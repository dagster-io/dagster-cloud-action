#!/usr/bin/env python3
import glob
import os
import re
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console

console = Console()

app = typer.Typer()


DAGSTER_OSS_BRANCH_OPTION = typer.Option(
    None,
    envvar="DAGSTER_OSS_BRANCH",
    help="The OSS git branch that is used to build dagster and other packages.",
)
DAGSTER_OSS_VERSION_OPTION = typer.Option(
    None,
    envvar="DAGSTER_OSS_VERSION",
    help="The version of the OSS dagster package to use.",
)


@contextmanager
def chdir(path: str):
    repo_root = Path(__file__).parent.parent
    curdir = Path(os.curdir).absolute()
    try:
        os.chdir(repo_root / path)
        yield
    finally:
        os.chdir(curdir)


def info(msg):
    console.print(msg, style="blue")


def error(msg):
    console.print(msg, style="red")


@app.command()
def run_tests():
    info("Running tests")
    subprocess.run(["pytest", "tests", "-s"], check=True)


@app.command(help="Build dagster-cloud-action docker image from dagster-cloud.pex")
def build_docker_action(version_tag: str, publish_docker_action: bool = True):
    image_name = get_docker_action_image_name(version_tag)
    info(f"Building {image_name}")
    with chdir("."):
        output = subprocess.check_output(
            [
                "docker",
                "build",
                ".",
                "-f",
                "src/Dockerfile",
                "-t",
                image_name,
            ],
            encoding="utf-8",
        )
        print(output)
        if publish_docker_action:
            info(f"Publishing {image_name}")
            output = subprocess.check_output(
                [
                    "docker",
                    "push",
                    image_name,
                ],
                encoding="utf-8",
            )
            print(output)


@app.command(help="Build dagster-cloud.pex - invoked by the dagster-cloud-pex-builder image")
def build_dagster_cloud_pex(
    dagster_oss_branch: Optional[str] = DAGSTER_OSS_BRANCH_OPTION,
    dagster_oss_version: Optional[str] = DAGSTER_OSS_VERSION_OPTION,
):
    if dagster_oss_branch:
        info(f"Using dagster@{dagster_oss_branch} for dagster packages")
        dagster_pkg = f"git+https://github.com/dagster-io/dagster.git@{dagster_oss_branch}#egg=dagster&subdirectory=python_modules/dagster"
        dagster_cloud_cli_pkg = f"git+https://github.com/dagster-io/dagster.git@{dagster_oss_branch}#egg=dagster-cloud-cli&subdirectory=python_modules/libraries/dagster-cloud-cli"
        dagster_dg_pkg = f"git+https://github.com/dagster-io/dagster.git@{dagster_oss_branch}#egg=dagster-dg&subdirectory=python_modules/libraries/dagster-dg"
        dagster_pipes_pkg = f"git+https://github.com/dagster-io/dagster.git@{dagster_oss_branch}#egg=dagster-pipes&subdirectory=python_modules/dagster-pipes"
        dagster_shared_pkg = f"git+https://github.com/dagster-io/dagster.git@{dagster_oss_branch}#egg=dagster-shared&subdirectory=python_modules/libraries/dagster-shared"
    else:
        pin_str = f"=={dagster_oss_version}" if dagster_oss_version else ""
        info("Using PyPI for dagster package")
        dagster_pkg = f"dagster{pin_str}"
        dagster_cloud_cli_pkg = "dagster-cloud-cli"
        dagster_dg_pkg = "dagster-dg"
        dagster_pipes_pkg = "dagster-pipes"
        dagster_shared_pkg = "dagster-shared"

    complete_platform_args = []

    for json_file in {
        "x86_64_310.json",
        "x86_64_312.json",
        "aarch64_312.json",
    }:
        with open(os.path.join(os.path.dirname(__file__), "complete_platforms", json_file)) as f:
            complete_platform = f.read()
            complete_platform_args.append(f"--complete-platform={complete_platform}")

    info("Building generated/gha/dagster-cloud.pex")
    args = [
        "pex",
        dagster_cloud_cli_pkg,
        dagster_pkg,
        dagster_dg_pkg,
        dagster_pipes_pkg,
        dagster_shared_pkg,
        "PyGithub",
        "pex>=2.1.132,<3",
        "-o=dagster-cloud.pex",
        *complete_platform_args,
        "--pip-version=23.0",
        "--resolver-version=pip-2020-resolver",
        "--venv=prepend",
        "--sh-boot",
        "-vvvvv",
    ]
    print(f"Running {args}")
    output = subprocess.check_output(
        args,
        shell=False,
        encoding="utf-8",
    )
    print(output)
    shutil.move("dagster-cloud.pex", "generated/gha/dagster-cloud.pex")
    info("Built generated/gha/dagster-cloud.pex")


@app.command(help="Update dagster-cloud.pex")
def update_dagster_cloud_pex(
    dagster_oss_branch: Optional[str] = DAGSTER_OSS_BRANCH_OPTION,
    dagster_oss_version: Optional[str] = DAGSTER_OSS_VERSION_OPTION,
):
    # Map /generated on the docker image to our local generated folder
    map_folders = {"/generated": os.path.join(os.path.dirname(__file__), "..", "generated")}

    env_args = []
    if dagster_oss_branch:
        env_args.extend(["-e", f"DAGSTER_OSS_BRANCH={dagster_oss_branch}"])

    if dagster_oss_version:
        env_args.extend(["-e", f"DAGSTER_OSS_VERSION={dagster_oss_version}"])

    mount_args = []
    for target_folder, source_folder in map_folders.items():
        mount_args.extend(["--mount", f"type=bind,source={source_folder},target={target_folder}"])

    cmd = [
        "docker",
        "build",
        "--progress=plain",
        "-t",
        "dagster-cloud-pex-builder",
        "--platform=linux/amd64",
        "-f",
        os.path.join(os.path.dirname(__file__), "Dockerfile.dagster-cloud-pex-builder"),
        os.path.dirname(__file__),
    ]

    subprocess.run(cmd, check=True)

    cmd = [
        "docker",
        "run",
        "--platform=linux/amd64",
        *env_args,
        *mount_args,
        "-t",
        "dagster-cloud-pex-builder",
    ]
    subprocess.run(cmd, check=True)


@app.command()
def update_docker_action_references(
    version_tag,
    glob_patterns: List[str] = ["**/*yaml", "**/*yml"],
):
    image_name = get_docker_action_image_name(version_tag)
    previous_image_name = get_docker_action_image_name("dev")
    info(f"Updating references from {previous_image_name} to {image_name}")
    with chdir("."):
        for pattern in glob_patterns:
            for path in glob.glob(pattern, recursive=True):
                input_text = open(path, encoding="utf-8").read()
                text = input_text.replace(previous_image_name, image_name)
                if text != input_text:
                    print(path)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(text)


@app.command()
def create_rc(
    version_tag: str,
    check_workdir: bool = True,
    execute_tests: bool = True,
    publish_docker_action: bool = True,
    dagster_oss_branch: Optional[str] = DAGSTER_OSS_BRANCH_OPTION,
    dagster_oss_version: Optional[str] = DAGSTER_OSS_VERSION_OPTION,
):
    if check_workdir:
        ensure_clean_workdir()
    branch = ensure_in_branch()
    info(f"Preparing a new RC in {branch}")

    if version_tag != "dev" and not re.match(r"^[0-9.]+$", version_tag):
        error(f"Invalid version tag {version_tag}")
        sys.exit(1)

    update_dagster_cloud_pex(dagster_oss_branch, dagster_oss_version)
    if execute_tests:
        run_tests()
    build_docker_action(version_tag, publish_docker_action)
    update_docker_action_references(version_tag)
    info(f"Updated working directory for {version_tag}")


def ensure_clean_workdir():
    proc = subprocess.run(["git", "status", "--porcelain"], capture_output=True, check=False)
    if proc.stdout or proc.stderr:
        error("ERROR: Git working directory not clean:")
        error((proc.stdout + proc.stderr).decode("utf-8"))
        sys.exit(1)


def ensure_in_branch():
    branch = get_branch_name()
    if branch == "main":
        error("ERROR: Not in branch")
        sys.exit(1)
    return branch


def get_branch_name():
    proc = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, check=True
    )
    return proc.stdout.decode("utf-8").strip()


def get_docker_action_image_name(version_tag: str) -> str:
    return f"ghcr.io/dagster-io/dagster-cloud-action:{version_tag}"


if __name__ == "__main__":
    try:
        app()
    except subprocess.CalledProcessError as err:
        error("Subprocess failed")
        error(err.args)
        if err.output:
            error(err.output.decode("utf-8"))
        if err.stderr:
            error(err.stderr.decode("utf-8"))
        raise
        sys.exit(2)
