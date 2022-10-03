# Build deps.pex, given a project root

import os
import os.path
import shutil
import tempfile
import setuptools
import sys
from . import util


def build_source_pex(code_directory, output_directory):

    os.makedirs(output_directory, exist_ok=True)
    out_pex_path = os.path.join(output_directory, "source.pex")

    # determine the top level source packages in the project
    source_packages = setuptools.find_packages(code_directory)
    source_packages = [
        pkg for pkg in source_packages if not pkg.endswith("_tests") and "." not in pkg
    ]
    print("Including packages:", source_packages)

    # need a new directory with just the source pakcages
    # create under project root so hard link works
    with tempfile.TemporaryDirectory() as src_dir:
        for pkg in source_packages:
            source_path = os.path.join(code_directory, pkg)
            dest_path = os.path.join(src_dir, pkg)
            shutil.copytree(source_path, dest_path)

        # now we can make the pex with just the source packages
        util.run_pex_command(["-D", src_dir, "-o", out_pex_path])

    print("Built", out_pex_path)
    print("Pex hash:", util.get_pex_info(out_pex_path)["pex_hash"])


if __name__ == "__main__":
    build_source_pex(sys.argv[1], sys.argv[2])
