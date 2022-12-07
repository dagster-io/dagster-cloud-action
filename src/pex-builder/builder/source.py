# Build source.pex, given a project root

import logging
import os
import os.path
import shutil
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

    curdir = os.curdir
    os.chdir(code_directory)
    try:
        with tempfile.TemporaryDirectory() as build_dir, tempfile.TemporaryDirectory() as sources_dir:
            included_dirs = []

            if os.path.exists("setup.py"):
                python_interpreter = util.python_interpreter_for(python_version)
                logging.info(f"Building packages using {python_interpreter} setup.py build")

                # build setup.py with the python version specified
                command = [
                    python_interpreter,
                    "setup.py",
                    "build",
                    "--build-lib",
                    build_dir,
                ]
                subprocess.run(command, capture_output=True, check=True)
                included_dirs.append(build_dir)
            else:
                logging.info(f"No setup.py found in {code_directory!r}, will only include source.")

            # We always include the source in a special package called working_directory.
            logging.info(
                "Bunding the source %r into the 'working_directory' package", code_directory
            )
            _prepare_working_directory(code_directory, sources_dir)
            included_dirs.append(sources_dir)

            # note this may include tests directories
            util.build_pex(
                included_dirs,
                requirements_filepaths=[],
                pex_flags=util.get_pex_flags(python_version),
                output_pex_path=tmp_pex_path,
            )
    finally:
        os.chdir(curdir)


def _prepare_working_directory(code_directory, sources_directory):
    # Copy code_directory contents into a package called working_directory under sources_directory
    package_dir = os.path.join(sources_directory, "working_directory")
    os.makedirs(package_dir, exist_ok=True)

    with open(os.path.join(package_dir, "__init__.py"), "w", encoding="utf-8") as init_file:
        init_file.write("# Auto generated package containing the original source at root/")

    shutil.copytree(
        code_directory, os.path.join(package_dir, "root"), copy_function=os.link, dirs_exist_ok=True
    )


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
