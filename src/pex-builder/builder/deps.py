# Build deps.pex, given a project root

import hashlib
import logging
import os
import os.path
import re
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List, Tuple

import click
import pkg_resources
from packaging import version

from . import util

STANDARD_PACKAGES = [
    # improves debugging as per https://pex.readthedocs.io/en/latest/recipes.html#long-running-pex-applications-and-daemons
    "setproctitle",
]


@dataclass(frozen=True)
class DepsRequirements:
    requirements_txt: str
    python_version: version.Version
    pex_flags: List[str]

    @property
    def hash(self) -> str:
        # The hash uniquely identifies the list of requirements used to build a deps.pex.
        # This is used as part of the cache key to reuse a cached deps.pex.
        # Note requirements_txt may have floating dependencies, so this is not perfect and may
        # reuse deps.pex even if a new PyPI package is published for a dependency.
        # An easy workaround is to pin the dependency in setup.py.
        return hashlib.sha1(
            (repr(self.requirements_txt) + str(self.python_version) + repr(self.pex_flags)).encode(
                "utf-8"
            )
        ).hexdigest()


def get_deps_requirements(code_directory, python_version: version.Version) -> DepsRequirements:

    # Combine dependencies specified in requirements.txt and setup.py
    lines = get_requirements_txt_deps(code_directory)
    lines.extend(get_setup_py_deps(code_directory))
    lines.extend(STANDARD_PACKAGES)

    deps_requirements_text = "\n".join(
        sorted(set(lines)) + [""]
    )  # empty string adds trailing newline

    logging.info("List of dependencies: %r", deps_requirements_text)
    deps_requirements = DepsRequirements(
        requirements_txt=deps_requirements_text,
        python_version=python_version,
        pex_flags=util.get_pex_flags(python_version),
    )
    logging.info("deps_requirements_hash: %r", deps_requirements.hash)
    return deps_requirements


def build_deps_pex(code_directory, output_directory, python_version) -> Tuple[str, str]:
    requirements = get_deps_requirements(code_directory, python_version)
    return build_deps_from_requirements(requirements, output_directory)


def build_deps_from_requirements(
    requirements: DepsRequirements,
    output_directory: str,
) -> Tuple[str, str]:
    """Builds deps-<HASH>.pex and returns the path to that file and the dagster version."""
    os.makedirs(output_directory, exist_ok=True)
    deps_requirements_path = os.path.join(
        output_directory, f"deps-requirements-{requirements.hash}.txt"
    )
    tmp_pex_path = os.path.join(output_directory, f"deps-from-{requirements.hash}.pex")

    with open(deps_requirements_path, "w", encoding="utf-8") as deps_requirements_file:
        deps_requirements_file.write(requirements.requirements_txt)

    logging.info(f"Building deps pex for Python version {requirements.python_version}")
    proc = util.build_pex(
        sources_directories=[],
        requirements_filepaths=[deps_requirements_path],
        pex_flags=requirements.pex_flags,
        output_pex_path=tmp_pex_path,
        # isolate this pex root from others on same machine. particularly useful in github action
        # environment where pex_root for builder.pex may get shared with this pex_root
        pex_root=os.path.join(output_directory, ".pex"),
    )
    if proc.returncode:
        logging.error("Failed to build deps.pex")
        logging.error(proc.stdout)
        logging.error(proc.stderr)

    pex_info = util.get_pex_info(tmp_pex_path)
    pex_hash = pex_info["pex_hash"]
    final_pex_path = os.path.join(output_directory, f"deps-{pex_hash}.pex")
    os.rename(tmp_pex_path, final_pex_path)
    logging.info("Wrote deps pex: %r", final_pex_path)

    distribution_names = pex_info["distributions"].keys()
    # the distribution is named something like 'dagster-1.0.14-py3-none-any.whl'
    pattern = re.compile("dagster-(.+?)-py")
    for name in distribution_names:
        match = pattern.match(name)
        if match:
            dagster_version = match.group(1)
            break
    else:
        raise ValueError("Did not find a dagster distribution in the deps pex")
    return final_pex_path, dagster_version


def get_requirements_txt_deps(code_directory: str) -> List[str]:
    requirements_path = os.path.join(code_directory, "requirements.txt")
    if not os.path.exists(requirements_path):
        return []

    # remove current dir from the deps
    return [
        line
        for line in open(requirements_path, encoding="utf-8").read().splitlines()
        if line not in {"", "."}
    ]


def get_setup_py_deps(code_directory: str) -> List[str]:
    setup_py_path = os.path.join(code_directory, "setup.py")
    if not os.path.exists(setup_py_path):
        raise ValueError("setup.py not found", setup_py_path)

    lines = []
    # write out egg_info files and load as distribution
    with tempfile.TemporaryDirectory() as temp_dir:
        proc = subprocess.run(
            ["python", setup_py_path, "egg_info", f"--egg-base={temp_dir}"],
            capture_output=True,
            check=False,
        )
        if proc.returncode:
            raise ValueError(
                "Error running setup.py egg_info: "
                + proc.stdout.decode("utf-8")
                + proc.stderr.decode("utf-8")
            )
        # read in requirements using pkg_resources
        dists = list(pkg_resources.find_distributions(temp_dir))
        if len(dists) != 1:
            raise ValueError(f"Could not find distribution for {setup_py_path}")
        dist = dists[0]
        for requirement in dist.requires():
            # the str() for Requirement is correctly formatted requirement
            # https://setuptools.pypa.io/en/latest/pkg_resources.html#requirement-methods-and-attributes
            lines.append(str(requirement))

    return lines


@click.command()
@click.argument("project_dir", type=click.Path(exists=True))
@click.argument("build_output_dir", type=click.Path(exists=False))
@util.python_version_option()
def deps_main(project_dir, build_output_dir, python_version):
    deps_pex_path, dagster_version = build_deps_pex(
        project_dir, build_output_dir, util.parse_python_version(python_version)
    )
    print(f"Wrote: {deps_pex_path} which includes dagster version {dagster_version}")


if __name__ == "__main__":
    deps_main()
