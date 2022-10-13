# Build source.pex, given a project root

import logging
import os
import os.path
import shutil
import tempfile
import setuptools
import subprocess
import sys
from . import util


def build_source_pex(code_directory, output_directory):
    os.makedirs(output_directory, exist_ok=True)
    code_directory = os.path.abspath(code_directory)
    tmp_pex_path = os.path.join(output_directory, f"source-{hash(code_directory)}.pex")

    build_pex_using_setup_py(code_directory, tmp_pex_path)

    pex_info = util.get_pex_info(tmp_pex_path)
    pex_hash = pex_info["pex_hash"]
    pex_name = f"source-{pex_hash}.pex"
    final_pex_path = os.path.join(output_directory, pex_name)
    os.rename(tmp_pex_path, final_pex_path)
    logging.info("Wrote source pex: %r", final_pex_path)
    return final_pex_path


def build_pex_using_setup_py(code_directory, tmp_pex_path):
    "Builds package using setup.py and copies built output into PEX."
    logging.info("Building packages using setup.py build")
    curdir = os.curdir
    os.chdir(code_directory)
    try:
        with tempfile.TemporaryDirectory() as build_dir:
            command = ["python", "setup.py", "build", "--build-lib", build_dir]
            subprocess.run(command, capture_output=True, check=True)
            # note this may include tests directories
            util.build_pex(
                [build_dir], requirements_filepaths=[], output_pex_path=tmp_pex_path
            )
    finally:
        os.chdir(curdir)


def build_pex_using_find_packages(code_directory, tmp_pex_path):
    """Finds all python packages and copies them into the PEX."""
    # determine the top level source packages in the project
    source_packages = setuptools.find_packages(code_directory)
    source_packages = [
        pkg for pkg in source_packages if not pkg.endswith("_tests") and "." not in pkg
    ]
    if not source_packages:
        raise ValueError("No packages found", code_directory)
    logging.info("Including packages for source pex: %r", source_packages)

    # need a new directory with just the source pakcages
    # create under project root so hard link works
    with tempfile.TemporaryDirectory() as src_dir:
        for pkg in source_packages:
            source_path = os.path.join(code_directory, pkg)
            dest_path = os.path.join(src_dir, pkg)
            # use os.link to just create hard links instead of actually copying all files over
            shutil.copytree(source_path, dest_path, copy_function=os.link)

        # now we can make the pex with just the source packages
        util.build_pex(
            [src_dir], requirements_filepaths=[], output_pex_path=tmp_pex_path
        )


if __name__ == "__main__":
    build_source_pex(sys.argv[1], sys.argv[2])
