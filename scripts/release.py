#!/usr/bin/env python3
from contextlib import contextmanager
import glob
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import List

import typer
from rich.console import Console

console = Console()

app = typer.Typer()


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
    subprocess.run(["pytest", "tests"], check=True)


@app.command()
def build_docker_action(version_tag: str, publish_docker_action: bool = True):
    pattern = get_docker_action_image_name('.+?"')
    image_name = get_docker_action_image_name(version_tag)
    info(f"Building {image_name}")
    with chdir("src"):
        output = subprocess.check_output(
            [
                "docker",
                "build",
                ".",
                "-t",
                image_name,
            ],
            encoding="utf-8",
        )
        print(output)
        if publish_docker_action:
            info(f"Publishing {image_name}")
            subprocess.check_output(
                [
                    "docker",
                    "push",
                    image_name,
                ],
                encoding="utf-8",
            )
            print(output)


@app.command()
def update_dagster_cloud_pex():
    with chdir("src/pex-builder"):
        info("Building generated/gha/dagster-cloud.pex")
        output = subprocess.check_output(
            "./build-dagster-cloud-pex.sh", shell=True, encoding="utf-8"
        )
        print(output)
        shutil.move("dagster-cloud.pex", "../../generated/gha/dagster-cloud.pex")


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


@app.command()
def create_rc(
    version_tag: str,
    previous_version_tag: str,
    check_workdir: bool = True,
    execute_tests: bool = True,
    publish_docker_action: bool = True,
):
    if check_workdir:
        ensure_clean_workdir()
    branch = ensure_in_branch()
    info(f"Preparing a new RC in {branch}")

    if not re.match(r"^[0-9.]+$", version_tag):
        error(f"Invalid version tag {version_tag}")
        sys.exit(1)

    update_dagster_cloud_pex()
    if execute_tests:
        run_tests()
    build_docker_action(version_tag, publish_docker_action)
    update_docker_action_references(previous_version_tag, version_tag)
    info(f"Updated working directory for {version_tag}")


def ensure_clean_workdir():
    proc = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, check=False
    )
    if proc.stdout or proc.stderr:
        error("ERROR: Git working directory not clean:")
        error((proc.stdout + proc.stderr).decode("utf-8"))
        sys.exit(1)


def ensure_in_branch():
    branch = get_branch_name()
    if branch != "main":
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
