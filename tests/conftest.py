import os
from pathlib import Path
import subprocess
import tempfile
from typing import Dict

import pytest

from . import command_stub


class ExecContext:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.environ = os.environ.copy()
        self.add_path(self.temp_dir)

        self.proc = None

    def tmpfile(self, filename):
        return os.path.join(self.temp_dir, filename)

    def set_env(self, environ: Dict[str, str]):
        self.environ.update(environ)

    def add_path(self, path):
        if self.environ.get("PATH"):
            self.environ["PATH"] = str(path) + ":" + self.environ["PATH"]
        else:
            self.environ["PATH"] = str(path)

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

        command_stub.generate(self.tmpfile(cmdname), commands_map)

    def run(self, command: str):
        """Runs command in the exec context"""
        with open(self.tmpfile("main.sh"), "w") as main_script:
            main_script.write("#!/bin/bash\n")
            main_script.write(
                command
                + f' > {self.tmpfile("output-stdout.txt")}  2> {self.tmpfile("output-stderr.txt")}\n'
            )
            main_script.write(f'echo $? > {self.tmpfile("output-exitcode.txt")}\n')
            main_script.write(f'env > {self.tmpfile("output-env.txt")}\n')
        os.chmod(self.tmpfile("main.sh"), 0o700)
        self.proc = subprocess.run(
            ["main.sh"], env=self.environ, cwd=self.temp_dir, shell=True
        )

        exitcode = open(self.tmpfile("output-exitcode.txt")).read().strip()
        if exitcode != "0":
            raise ValueError(
                f"Exit code {exitcode} running {command!r}.\n"
                f"Stdout: {self.get_stdout()}\nError: {self.get_stderr()}"
            )

    def get_stdout(self) -> str:
        return open(self.tmpfile("output-stdout.txt")).read()

    def get_stderr(self) -> str:
        return open(self.tmpfile("output-stderr.txt")).read()

    def get_output_env(self) -> Dict[str, str]:
        env = {}
        for line in open(self.tmpfile("output-env.txt")):
            try:
                name, val = line.split("=", 1)
                env[name] = val.strip()
            except ValueError:
                pass
        return env

    def get_command_log(self, cmdname: str):
        return open(self.tmpfile(cmdname + ".log")).read().splitlines(keepends=False)

    def cleanup(self):
        pass
        # shutil.rmtree(self.temp_dir)


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
