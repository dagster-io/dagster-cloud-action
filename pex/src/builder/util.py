import json
import os
import subprocess
from typing import List
from zipfile import ZipFile


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
