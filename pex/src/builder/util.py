from contextlib import contextmanager
import json
import logging
import os
import subprocess
from typing import List
from zipfile import ZipFile

from dagster_cloud_cli import gql

logging.basicConfig(level=logging.INFO)

def run_self_module(module_name, args: List[str]):
    "Invoke this pex again with -m {module}"
    pex = os.getenv("PEX")
    if not pex:
        raise RuntimeError("Non running within a pex (env PEX not set)")
    args = [pex, "-m", module_name] + args
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

    dagster_cloud_url = os.getenv("DAGSTER_CLOUD_URL")
    if not dagster_cloud_url:
        raise ValueError("DAGSTER_CLOUD_URL not defined")

    url = f"{dagster_cloud_url}/{deployment_name}"

    with gql.graphql_client_from_url(url, dagster_cloud_api_token) as client:
        yield client
