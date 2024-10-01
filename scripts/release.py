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

DAGSTER_INTERNAL_BRANCH_OPTION = typer.Option(
    None,
    help="The internal git branch that is used to build dagster-cloud and other packages.",
)
DAGSTER_OSS_BRANCH_OPTION = typer.Option(
    None, help="The OSS git branch that is used to build dagster and other packages."
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


@app.command(help="Build dagster-cloud.pex")
def update_dagster_cloud_pex(
    dagster_internal_branch: Optional[str] = DAGSTER_INTERNAL_BRANCH_OPTION,
    dagster_oss_branch: Optional[str] = DAGSTER_OSS_BRANCH_OPTION,
):
    if dagster_internal_branch:
        info(
            f"Using internal@{dagster_internal_branch} for dagster-cloud, dagster-cloud-cli packages"
        )
        dagster_cloud_pkg = f"git+https://github.com/dagster-io/internal.git@{dagster_internal_branch}#egg=dagster-cloud&subdirectory=dagster-cloud/python_modules/dagster-cloud"
        dagster_cloud_cli_pkg = f"git+https://github.com/dagster-io/internal.git@{dagster_internal_branch}#egg=dagster-cloud-cli&subdirectory=dagster-cloud/python_modules/dagster-cloud-cli"
    else:
        info("Using PyPI for dagster-cloud, dagster-cloud-cli packages")
        dagster_cloud_pkg = "dagster-cloud"
        dagster_cloud_cli_pkg = "dagster-cloud-cli"

    if dagster_oss_branch:
        info(f"Using dagster@{dagster_internal_branch} for dagster package")
        dagster_pkg = f"git+https://github.com/dagster-io/dagster.git@{dagster_oss_branch}#egg=dagster&subdirectory=python_modules/dagster"
    else:
        info("Using PyPI for dagster package")
        dagster_pkg = "dagster"

    platform_args = []

    # each of the default versions used by ubuntu 20.04 / 22.04 / 24.04 respectively
    for py_version in ["38", "310", "312"]:
        platform_args.extend(
            [
                f"--platform=manylinux2014_x86_64-cp-{py_version}-cp{py_version}",
            ]
        )

    info("Building generated/gha/dagster-cloud.pex")
    args = [
        "pex",
        dagster_cloud_pkg,
        dagster_cloud_cli_pkg,
        dagster_pkg,
        "PyGithub",
        "-o=dagster-cloud.pex",
        *platform_args,
        "--platform=macosx_12_0_x86_64-cp-311-cp311",
        "--platform=macosx_12_0_arm64-cp-311-cp311",
        "--pip-version=23.0",
        "--resolver-version=pip-2020-resolver",
        "--venv=prepend",
        # use a /bin/sh entrypoint that is better at choosing a python interpreter to use
        "--sh-boot",
        "-v",
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


@app.command()
def update_docker_action_references(
    previous_version_tag,
    version_tag,
    glob_patterns: List[str] = ["**/*yaml", "**/*yml"],
):
    image_name = get_docker_action_image_name(version_tag)
    previous_image_name = get_docker_action_image_name(previous_version_tag)
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
    previous_version_tag: str,
    check_workdir: bool = True,
    execute_tests: bool = True,
    publish_docker_action: bool = True,
    dagster_internal_branch: Optional[str] = DAGSTER_INTERNAL_BRANCH_OPTION,
    dagster_oss_branch: Optional[str] = DAGSTER_OSS_BRANCH_OPTION,
):
    if check_workdir:
        ensure_clean_workdir()
    branch = ensure_in_branch()
    info(f"Preparing a new RC in {branch}")

    if not re.match(r"^[0-9.]+$", version_tag):
        error(f"Invalid version tag {version_tag}")
        sys.exit(1)

    update_dagster_cloud_pex(dagster_internal_branch, dagster_oss_branch)
    if execute_tests:
        run_tests()
    build_docker_action(version_tag, publish_docker_action)
    update_docker_action_references(previous_version_tag, version_tag)
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
