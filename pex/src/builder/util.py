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
    proc = subprocess.run(args, capture_output=True)
    return proc


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
