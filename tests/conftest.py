import importlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict
from unittest import mock

import requests
import pytest

from . import command_stub


class ExecContext:
    def __init__(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.environ = {}
        self.proc = None

    def tmp_file_path(self, filename) -> Path:
        "Return a Path object pointing to named file in tmp_dir."
        return Path(self.tmp_dir) / filename

    def tmp_file_content(self, filename):
        return self.tmp_file_path(filename).read_text()

    def set_env(self, environ: Dict[str, str]):
        self.environ.update(environ)

    def stub_command(self, cmdname, commands_map: Dict[str, str]):
        """Generate a fake command called cmdname.

        The cmdname accepts cmd line args exactly matching any dictionary key and
        prints the dictionary value to stdout.

        Eg this creates a fake dagster-cloud command that works for exactly the cmdline specified:

        stub_command(
            'dagster-cloud',
            {'serverless registry-info --url "url" --api-token "token"':
             'AWS_ECR_USERNAME=username\nAWS_ECR_PASSWORD=password\n'})
        """

        command_stub.generate(str(self.tmp_file_path(cmdname)), commands_map)

    def prepare_run_script(self, command: str, target_tmp_dir=None) -> Path:
        """Create a shell script for running command and return script path."""
        script_name = "main.sh"
        script_path = self.tmp_file_path(script_name)
        with open(script_path, "w") as main_script:
            main_script.write("#!/bin/bash\n")
            # write env vars

            for env_name, env_value in self.environ.items():
                # map any tmp_dir paths to the target_tmp_dir, useful for docker mounts
                tmp_dir_path = Path(self.tmp_dir)
                if (
                    target_tmp_dir
                    and isinstance(env_value, Path)
                    and tmp_dir_path in env_value.parents
                ):
                    tail = env_value.relative_to(tmp_dir_path)
                    env_value = Path(target_tmp_dir) / tail
                main_script.write(f"export {env_name}='{env_value}'\n")

            # adjust curdir and PATH
            # this ensures the stub commands get invoked and not any other commands available
            # elsewhere on PATH
            main_script.write('cd "$(dirname "$0")"\n')
            main_script.write("export PATH=.:$PATH\n")

            # invoke main command
            main_script.write(
                command + " > ./output-stdout.txt 2> ./output-stderr.txt\n"
            )

            # save returncode and final env vars
            main_script.write(f"echo $? > ./output-exitcode.txt\n")
            main_script.write(f"env > ./output-env.txt\n")

        os.chmod(script_path, 0o700)
        return script_path

    def post_run(self, command):
        exitcode = open(self.tmp_file_path("output-exitcode.txt")).read().strip()
        if exitcode != "0":
            raise ValueError(
                f"Exit code {exitcode} running {command!r}.\n"
                f"Stdout: {self.get_stdout()}\nError: {self.get_stderr()}"
            )

    def run_local_command(self, command: str):
        """Runs command (full path to any executable) in the exec context"""
        if self.proc:
            # various input/output filenames are not unique in the tempdir so we can only run once
            raise ValueError("ExecContext can only be run once")

        script_path = self.prepare_run_script(command)
        print("Running:", script_path)
        self.proc = subprocess.run([script_path], shell=True, check=True)
        self.post_run(command)

    def run_docker_command(self, docker_image_tag, command):
        """Invokes command inside a docker image, mapping this exec context to the docker container."""
        if self.proc:
            raise ValueError("ExecContext can only be run once")

        volume_mount_flag = f"-v{self.tmp_dir}:/mount"
        script_path = self.prepare_run_script(command, target_tmp_dir="/mount")
        docker_script_path = f"/mount/{os.path.basename(script_path)}"
        docker_args = [
            "docker",
            "run",
            volume_mount_flag,
            docker_image_tag,
            docker_script_path,
        ]
        print("Running:", docker_args)

        self.proc = subprocess.run(
            docker_args,
            # shell=True,
            check=True,
        )

        self.post_run(command)

    def get_stdout(self) -> str:
        return self.tmp_file_content("output-stdout.txt")

    def get_stderr(self) -> str:
        return self.tmp_file_content("output-stderr.txt")

    def get_output_env(self) -> Dict[str, str]:
        env = {}
        for line in self.tmp_file_content("output-env.txt").splitlines():
            try:
                name, val = line.split("=", 1)
                env[name] = val.strip()
            except ValueError:
                pass
        return env

    def get_command_log(self, cmdname: str):
        return self.tmp_file_content(cmdname + ".log").splitlines(keepends=False)

    def cleanup(self):
        shutil.rmtree(self.tmp_dir)


@pytest.fixture(scope="function")
def exec_context():
    ec = ExecContext()
    try:
        yield ec
    finally:
        ec.cleanup()


@pytest.fixture(scope="session")
def repo_root():
    return Path(os.path.abspath(__file__)).parents[1]


@pytest.fixture(scope="session")
def action_docker_image_id(repo_root):
    "Build a docker image using local source and return the tag"
    _, iidfile = tempfile.mkstemp()
    try:
        proc = subprocess.run(
            ["docker", "buildx", "build", ".", "--load", "--iidfile", iidfile],
            cwd=repo_root / "src",
            check=True,
            capture_output=True,
        )
        return open(iidfile).read().strip()
    finally:
        os.remove(iidfile)


@pytest.fixture(scope="session")
def builder_pex_path(repo_root):
    "Path to a freshly built builder.pex file, can be run as a subprocess."
    # To cut down test time during local iteration, build once and reuse
    # yield repo_root / "src/pex-builder/build/builder.pex"

    with tempfile.TemporaryDirectory() as tmpdir:
        proc = subprocess.run(
            ["./build-builder.sh", tmpdir],
            cwd=repo_root / "src/pex-builder",
            check=True,
            capture_output=True,
        )
        path = os.path.join(tmpdir, "builder.pex")
        if not os.path.exists(path):
            raise ValueError("builder.pex not created:" + proc.stderr.decode("utf-8"))
        yield path


@pytest.fixture(scope="session")
def builder_module(builder_pex_path):
    "Imported builder module object, for in-process testing of builder code."
    # This contains the same code as the builder.pex, but using it as a module
    # makes patching easier. To make sure we use the same dependencies that are
    # packed in builder.pex, we unpack builder.pex to a venv and add the venv
    # directory to sys.path.

    with tempfile.TemporaryDirectory() as venv_dir:
        try:
            # special invocation to have builder.pex unpack itself
            subprocess.check_output(
                [builder_pex_path, "venv", venv_dir],
                env={"PEX_TOOLS": "1", **os.environ},
                stderr=subprocess.STDOUT,
                encoding="utf-8",
            )
        except subprocess.CalledProcessError as exc:
            raise ValueError("Could not unpack builder:" + exc.output)
        sys.path.insert(0, os.path.join(venv_dir, "lib/python3.8/site-packages"))
        try:
            yield importlib.import_module("builder")
        finally:
            sys.path.pop(0)


@pytest.fixture(scope="function")
def pex_registry_fixture():
    # replaces remote registry with a python dictionary, which is returned by this fixture
    # note this fixture only works with builder_module, not builder_pex_path

    s3_objects = {}  # filename -> content

    def s3_urls_for_get(filenames):
        return [
            (filename if filename in s3_objects else None) for filename in filenames
        ]

    def s3_urls_for_put(filenames):
        return filenames

    # Consider switching to the "responses" package
    def requests_get(url):
        response = requests.Response()
        if url in s3_objects:
            response._content = s3_objects[url]
            response.status_code = 200
        else:
            response.status_code = 404
        return response

    def requests_put(url, data):
        s3_objects[url] = data.read() if hasattr(data, "read") else data
        response = requests.Response()
        response.status_code = 200
        return response

    with mock.patch(
        "builder.pex_registry.get_s3_urls_for_get", s3_urls_for_get
    ) as _, mock.patch(
        "builder.pex_registry.get_s3_urls_for_put", s3_urls_for_put
    ) as _, mock.patch(
        "requests.get", requests_get
    ) as _, mock.patch(
        "requests.put", requests_put):
        yield s3_objects