# Build deps.pex, given a project root

from dataclasses import dataclass
import glob
import hashlib
import logging
import os
import os.path
import subprocess
import sys
import tempfile
from typing import List

from . import util


@dataclass(frozen=True)
class DepsRequirements:
    hash: str
    requirements_txt: str


def get_deps_requirements(code_directory) -> DepsRequirements:

    # Combine dependencies specified in requirements.txt and setup.py
    lines = get_requirements_txt_deps(code_directory)
    lines.extend(get_setup_py_deps(code_directory))

    deps_requirements_text = "\n".join(sorted(lines))
    # note requirements.txt may have floating dependencies, so this is not perfect
    deps_requirements_hash = hashlib.sha1(
        deps_requirements_text.encode("utf-8")
    ).hexdigest()

    logging.info("List of dependencies: %r", deps_requirements_text)
    logging.info("deps_requirements_hash: %r", deps_requirements_hash)
    return DepsRequirements(
        hash=deps_requirements_hash, requirements_txt=deps_requirements_text
    )


def build_deps_pex(code_directory, output_directory) -> str:
    requirements = get_deps_requirements(code_directory)
    return build_deps_from_requirements(requirements, output_directory)


def build_deps_from_requirements(
    requirements: DepsRequirements, output_directory: str
) -> str:
    """Builds deps-<HASH>.pex and returns the path to that file."""
    os.makedirs(output_directory, exist_ok=True)
    deps_requirements_path = os.path.join(
        output_directory, f"deps-requirements-{requirements.hash}.txt"
    )
    tmp_pex_path = os.path.join(output_directory, f"deps-from-{requirements.hash}.pex")

    with open(deps_requirements_path, "w") as deps_requirements_file:
        deps_requirements_file.write(requirements.requirements_txt)

    logging.info("Building deps pex...")
    util.run_pex_command(["-r", deps_requirements_path, "-o", tmp_pex_path])

    pex_info = util.get_pex_info(tmp_pex_path)
    pex_hash = pex_info["pex_hash"]
    final_pex_path = os.path.join(output_directory, f"deps-{pex_hash}.pex")
    os.rename(tmp_pex_path, final_pex_path)
    logging.info("Wrote deps pex: %r", final_pex_path)
    return final_pex_path


def get_requirements_txt_deps(code_directory: str) -> List[str]:
    requirements_path = os.path.join(code_directory, "requirements.txt")
    if not os.path.exists(requirements_path):
        return []

    # remove current dir from the deps
    return [
        line
        for line in open(requirements_path).read().splitlines()
        if line not in {"", "."}
    ]


def get_setup_py_deps(code_directory: str) -> List[str]:
    setup_py_path = os.path.join(code_directory, "setup.py")
    if not os.path.exists(setup_py_path):
        raise ValueError("setup.py not found", setup_py_path)

    lines = []
    # write out egg_info files and read requires.txt
    with tempfile.TemporaryDirectory() as temp_dir:
        subprocess.run(
            ["python", setup_py_path, "egg_info", f"--egg-base={temp_dir}"], check=True
        )
        for path in glob.glob(os.path.join(temp_dir, "*/requires.txt")):
            lines.extend(open(path).read().splitlines())

    return lines


if __name__ == "__main__":
    deps_pex_path = build_deps_pex(sys.argv[1], sys.argv[2])
    print(f"Wrote: {deps_pex_path}")
