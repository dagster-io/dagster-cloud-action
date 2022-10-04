# Build deps.pex, given a project root

import code
import logging
import os
import os.path
import shutil
import tempfile
import setuptools
import sys
from . import util


def build_source_pex(code_directory, output_directory):
    os.makedirs(output_directory, exist_ok=True)
    code_directory = os.path.abspath(code_directory)
    tmp_pex_path = os.path.join(output_directory, f"source-{hash(code_directory)}.pex")

    # determine the top level source packages in the project
    source_packages = setuptools.find_packages(code_directory)
    source_packages = [
        pkg for pkg in source_packages if not pkg.endswith("_tests") and "." not in pkg
    ]
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
        util.run_pex_command(["-D", src_dir, "-o", tmp_pex_path])

    pex_info = util.get_pex_info(tmp_pex_path)
    pex_hash = pex_info["pex_hash"]
    final_pex_path = os.path.join(output_directory, f"source-{pex_hash}.pex")
    os.rename(tmp_pex_path, final_pex_path)
    logging.info("Wrote source pex: %r", final_pex_path)
    return final_pex_path


if __name__ == "__main__":
    build_source_pex(sys.argv[1], sys.argv[2])
