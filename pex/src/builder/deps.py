# Build deps.pex, given a project root

from dataclasses import dataclass
import hashlib
import os
import os.path
import sys
from typing import Dict

from . import util


@dataclass(frozen=True)
class DepsRequirements:
    hash: str
    requirements_txt: str


def get_deps_requirements(project_root) -> DepsRequirements:
    requirements_path = os.path.join(project_root, "requirements.txt")
    if not os.path.exists(requirements_path):
        raise ValueError("Expected file not found", requirements_path)

    lines = open(requirements_path).read().splitlines()

    # generate a new requirements file
    # remove current dir from the deps
    lines = [line for line in lines if line not in {"", "."}]
    # add other required deps (currently specified in setup.py)
    lines.extend(["dagster", "dagster_aws"])
    deps_requirements_text = "\n".join(sorted(lines))
    # note requirements.txt may have floating dependencies, so this is not perfect
    deps_requirements_hash = hashlib.sha1(
        deps_requirements_text.encode("utf-8")
    ).hexdigest()

    return DepsRequirements(
        hash=deps_requirements_hash, requirements_txt=deps_requirements_text
    )


def build_deps_pex(project_root, output_dir) -> str:
    requirements = get_deps_requirements(project_root)
    # TODO: if requirements.hash is already built, skip next step
    return build_deps_from_requirements(requirements, output_dir)


def build_deps_from_requirements(
    requirements: DepsRequirements, output_dir: str
) -> str:
    os.makedirs(output_dir, exist_ok=True)
    deps_requirements_path = os.path.join(
        output_dir, f"deps-requirements-{requirements.hash}.txt"
    )
    tmp_pex_path = os.path.join(output_dir, f"deps-from-{requirements.hash}.pex")

    with open(deps_requirements_path, "w") as deps_requirements_file:
        deps_requirements_file.write(requirements.requirements_txt)

    util.run_pex_command(["-r", deps_requirements_path, "-o", tmp_pex_path])

    pex_info = util.get_pex_info(tmp_pex_path)
    pex_hash = pex_info["pex_hash"]
    final_pex_path = os.path.join(output_dir, f"deps-{pex_hash}.pex")
    os.rename(tmp_pex_path, final_pex_path)
    return final_pex_path


if __name__ == "__main__":
    deps_pex_path = build_deps_pex(sys.argv[1], sys.argv[2])
    print(f"Wrote: {deps_pex_path}")
