import json
import logging
import os
import subprocess
import sys
from contextlib import contextmanager
from typing import List, Optional
from zipfile import ZipFile

import click
from dagster_cloud_cli import gql
from packaging import version

TARGET_PYTHON_VERSIONS = [
    version.Version(python_version) for python_version in ["3.8", "3.9", "3.10"]
]


def run_python_subprocess(args: List[str], env=None):
    """Invoke python with given args, using an environment identical to current environment."""
    # If running a pex file directly, we invoke the executable pex file again.
    # Otherwise we assume we're running in a pex generated venv and use the python executable.
    cmd = os.getenv("PEX", sys.executable)

    args = [cmd] + args
    logging.info("Running %r in %r", args, os.path.abspath(os.curdir))
    proc = subprocess.run(args, capture_output=True, env=env, check=False)
    return proc


def run_self_module(module_name, args: List[str]):
    "Invoke this executable again with -m {module}"
    return run_python_subprocess(["-m", module_name, *args])


def get_pex_flags(python_version: version.Version) -> List[str]:
    "python_version should includes the major and minor version only, eg Version('3.8')"
    if python_version not in TARGET_PYTHON_VERSIONS:
        raise ValueError(
            f"Unsupported python version {python_version}. Supported: {TARGET_PYTHON_VERSIONS}."
        )
    version_tag = f"{python_version.major}{python_version.minor}"  # eg '38'
    python_interpreter = python_interpreter_for(python_version)
    return [
        # extra check to ensure run environment matches built version
        f"--python={python_interpreter}",
        # use the dependency for the general linux distribution for the major/minor python version
        f"--platform=manylinux2014_x86_64-cp-{version_tag}-cp{version_tag}",
        # resolves dependencies using the local interpreter, effectively allowing source distributions
        # to work (since they can be build by the local interpreter)
        # see also https://linear.app/elementl/issue/CLOUD-2023/pex-builds-fail-for-dbt-core-dependency
        "--resolve-local-platforms",
        # this ensures PEX_PATH is not cleared and any subprocess invoked can also use this.
        # this is important for running console scripts that use the pex environment (eg dbt)
        "--no-strip-pex-env",
        # use a newer version of pip since it is more reliable
        # see https://github.com/pantsbuild/pex/issues/2003
        "--pip-version=22.2.2",
    ]


def build_pex(
    sources_directories: List[str],
    requirements_filepaths: List[str],
    pex_flags: List[str],
    output_pex_path: str,
    pex_root: Optional[str] = None,
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
    with linux on cloud.

    The python_version tuple eg ('3', '9') determines the target runtime environment. In theory
    we can build a pex in an environment without the target python version present.
    """
    flags = pex_flags.copy()
    if not sources_directories and not requirements_filepaths:
        raise ValueError("At least one of sources_directories or requirements_filepath required.")
    for src_dir in sources_directories:
        flags.extend(["-D", src_dir])
    for req_file in requirements_filepaths:
        flags.extend(["-r", req_file])
    pex_args = [*flags, "-o", output_pex_path]
    if pex_root:
        pex_args.extend(["--pex-root", pex_root])
    return run_pex_command(pex_args)


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
    return "files=" + ":".join(sorted(os.path.basename(filepath) for filepath in filepaths))


@contextmanager
def graphql_client(deployment_name: str):
    dagster_cloud_api_token = os.getenv("DAGSTER_CLOUD_API_TOKEN")
    if not dagster_cloud_api_token:
        raise ValueError("DAGSTER_CLOUD_API_TOKEN not defined")

    url = url_for_deployment(deployment_name)

    with gql.graphql_client_from_url(url, dagster_cloud_api_token) as client:
        yield client


def get_registry_info():
    with graphql_client("prod") as client:
        return gql.get_ecr_info(client)


def url_for_deployment(deployment_name):
    dagster_cloud_url = os.getenv("DAGSTER_CLOUD_URL")
    if not dagster_cloud_url:
        raise ValueError("DAGSTER_CLOUD_URL not defined")

    return f"{dagster_cloud_url}/{deployment_name}"


def python_interpreter_for(python_version: version.Version) -> str:
    return "python" + str(python_version)  # eg 'python3.8'


def python_version_option():
    "reusable click.option"
    return click.option(
        "--python-version",
        type=click.Choice([str(v) for v in TARGET_PYTHON_VERSIONS]),
        default="3.8",
        show_default=True,
        help="Target Python version.",
    )


def parse_python_version(python_version: str) -> version.Version:
    return version.Version(python_version)


def parse_kv(ctx, param: str, value: Optional[str]):  # pylint: disable=unused-argument
    if not value:
        return {}
    try:
        return dict(part.split("=", 1) for part in value.split(","))
    except ValueError as err:
        raise ValueError(f"Value {value!r} could not be parsed: {err}")
