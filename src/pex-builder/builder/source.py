# Build source.pex, given a project root

import logging
import os
import os.path
import subprocess
import tempfile
from uuid import uuid4

import click

from . import util


def build_source_pex(code_directory, output_directory, python_version):
    output_directory = os.path.abspath(output_directory)
    os.makedirs(output_directory, exist_ok=True)
    code_directory = os.path.abspath(code_directory)
    tmp_pex_path = os.path.join(output_directory, f"source-tmp-{uuid4()}.pex")

    build_pex_using_setup_py(code_directory, tmp_pex_path, python_version)

    pex_info = util.get_pex_info(tmp_pex_path)
    pex_hash = pex_info["pex_hash"]
    pex_name = f"source-{pex_hash}.pex"
    final_pex_path = os.path.join(output_directory, pex_name)
    os.rename(tmp_pex_path, final_pex_path)
    logging.info("Wrote source pex: %r", final_pex_path)
    return final_pex_path


def build_pex_using_setup_py(code_directory, tmp_pex_path, python_version):
    "Builds package using setup.py and copies built output into PEX."
    python_interpreter = util.python_interpreter_for(python_version)
    logging.info(f"Building packages using {python_interpreter} setup.py build")
    curdir = os.curdir
    os.chdir(code_directory)
    if not os.path.exists("setup.py"):
        raise ValueError(f"setup.py not found in {code_directory!r}")
    try:
        with tempfile.TemporaryDirectory() as build_dir:
            # build setup.py with the python version specified
            command = [
                python_interpreter,
                "setup.py",
                "build",
                "--build-lib",
                build_dir,
            ]
            subprocess.run(command, capture_output=True, check=True)
            # note this may include tests directories
            util.build_pex(
                [build_dir],
                requirements_filepaths=[],
                pex_flags=util.get_pex_flags(python_version),
                output_pex_path=tmp_pex_path,
            )
    finally:
        os.chdir(curdir)


@click.command()
@click.argument("project_dir", type=click.Path(exists=True))
@click.argument("build_output_dir", type=click.Path(exists=False))
@util.python_version_option()
def source_main(project_dir, build_output_dir, python_version):
    source_pex_path = build_source_pex(
        project_dir, build_output_dir, util.parse_python_version(python_version)
    )
    print(f"Wrote: {source_pex_path}")


if __name__ == "__main__":
    source_main()
