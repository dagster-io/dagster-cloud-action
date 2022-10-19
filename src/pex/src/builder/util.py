from contextlib import contextmanager
import json
import logging
import os
import subprocess
import sys
from typing import List
from zipfile import ZipFile

from dagster_cloud_cli import gql

logging.basicConfig(level=logging.INFO)


def run_self_module(module_name, args: List[str]):
    "Invoke this executable again with -m {module}"
    # If running a pex file directly, we invoke the executable pex file again.
    # Otherwise we assume we're running in a pex generated venv and use the python executable.
    cmd = os.getenv("PEX", sys.executable)

    args = [cmd, "-m", module_name] + args
    logging.info("Running %r", args)
    proc = subprocess.run(args, capture_output=True)
    return proc


def build_pex(
    sources_directories: List[str],
    requirements_filepaths: List[str],
    output_pex_path: str,
):
    """Invoke pex with common build flags and pass parameters through to specific pex flags

    sources_directories: passed to the pex -D flag (aka --source-directories)
    requirements_filepaths: passed to the pex -r flag (aka --requirement)

    Platform:
    For the pex --platform tag used below, see pex --help and
    https://peps.python.org/pep-0425/
    https://peps.python.org/pep-0427/

    Packages for the current platform are always included. (--platform=current)
    The manylinux platform ensures pexes built on local machines (macos, windows) are compatible
    with linux on cloud. For now we hardcode 'cp38' for CPython 3.8.
    TODO: Make Python version configurable.
    """
    flags = [
        "--interpreter-constraint=CPython>=3.8,<3.9",  # extra check to ensure run environment has py 3.8
        "--platform=current",
        f"--platform=manylinux2014_x86_64-cp-38-cp38",
    ]
    if not sources_directories and not requirements_filepaths:
        raise ValueError(
            "At least one of sources_directories or requirements_filepath required."
        )
    for src_dir in sources_directories:
        flags.extend(["-D", src_dir])
    for req_file in requirements_filepaths:
        flags.extend(["-r", req_file])
    return run_pex_command([*flags, "-o", output_pex_path])


def run_pex_command(args: List[str]):
    return run_self_module("pex", args)


def run_dagster_cloud_cli_command(args: List[str]):
    return run_self_module("dagster_cloud_cli.entrypoint", args)


def run_dagster_command(args: List[str]):
    return run_self_module("dagster", args)


def get_pex_info(pex_filepath):
    with ZipFile(pex_filepath) as pex_zip:
        return json.load(pex_zip.open("PEX-INFO"))


def build_pex_tag(filepaths: List[str]) -> str:
    return "files=" + ":".join(
        sorted(os.path.basename(filepath) for filepath in filepaths)
    )


@contextmanager
def graphql_client(deployment_name: str):
    dagster_cloud_api_token = os.getenv("DAGSTER_CLOUD_API_TOKEN")
    if not dagster_cloud_api_token:
        raise ValueError("DAGSTER_CLOUD_API_TOKEN not defined")

    url = url_for_deployment(deployment_name)

    with gql.graphql_client_from_url(url, dagster_cloud_api_token) as client:
        yield client


def url_for_deployment(deployment_name):
    dagster_cloud_url = os.getenv("DAGSTER_CLOUD_URL")
    if not dagster_cloud_url:
        raise ValueError("DAGSTER_CLOUD_URL not defined")

    return f"{dagster_cloud_url}/{deployment_name}"
