#!/usr/bin/env python

# Switches PEX deploy behavior based on github runner's ubuntu version
# - ubuntu-20.04 can always build pexes that work on our target platform
# - ubuntu-22.04 can only build pexes if there are no sdists (source only packages)

# On ubuntu-20.04: forward args to `dagster-cloud --build-method=local`
# On ubuntu-22.04: forward args to `dagster-cloud --build-method=docker`
# - Sometimes 22.04 may try to build sdists but build the wrong version (since we are not yet
#   using --complete-platform for pex). To avoid this situation, we always build dependencies in the
#   right docker environment on 22.04. Note if dependencies are not being built, docker will not
#   be used. The source.pex is always built using the local environment.

import os
from pathlib import Path
import subprocess
import sys
from typing import Optional

DAGSTER_CLOUD_PEX_PATH = (
    Path(__file__).parent.parent / "generated/gha/dagster-cloud.pex"
)


def main():
    args = sys.argv[1:]

    if os.getenv("GITHUB_EVENT_NAME") == "pull_request":
        print("Running in a pull request - going to do a branch deployment")
        deployment_name = get_branch_deployment_name()
    else:
        print("Going to do a full deployment.")
        deployment_name = None

    ubuntu_version = get_runner_ubuntu_version()
    print("Running on Ubuntu", ubuntu_version)
    if ubuntu_version == "20.04":
        returncode, output = deploy_pex(args, deployment_name, build_method="local")
    else:
        returncode, output = deploy_pex(args, deployment_name, build_method="docker")
    if returncode:
        print(
            "::error Title=Deploy failed::Failed to deploy Python Executable. "
            "Try disabling fast deploys by setting `ENABLE_FAST_DEPLOYS: 'false'` in your .github/workflows/*yml."
        )
        # TODO: fallback to docker deploy here
        sys.exit(1)


def get_runner_ubuntu_version():
    release_info = open("/etc/lsb-release", encoding="utf-8").read()
    # Example:
    # DISTRIB_ID=Ubuntu
    # DISTRIB_RELEASE=22.04
    # DISTRIB_CODENAME=jammy
    # DISTRIB_DESCRIPTION="Ubuntu 22.04.1 LTS"
    for line in release_info.splitlines(keepends=False):
        if line.startswith("DISTRIB_RELEASE="):
            return line.split("=", 1)[1]
    return "22.04"  # fallback to safer behavior


def run(args):
    # Prints streaming output and also captures and returns it
    print("Running", args)
    popen = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8"
    )
    output = []
    for line in iter(popen.stdout.readline, ""):
        print(line, end="")
        output.append(line)
    popen.stdout.close()
    returncode = popen.wait()
    return returncode, output


def get_branch_deployment_name():
    returncode, output = run(
        [
            str(DAGSTER_CLOUD_PEX_PATH),
            "-m",
            "dagster_cloud_cli.entrypoint",
            "ci",
            "branch-deployment",
        ]
    )
    if not returncode:
        print("Could not determine branch deployment")
        sys.exit(1)
    name = "".join(output).strip()
    print("Deploying to branch deployment:", name)
    return name


def deploy_pex(args, deployment_name: Optional[str], build_method: str):
    dagster_cloud_yaml = args.pop(0)
    args.insert(0, os.path.dirname(dagster_cloud_yaml))
    args = args + [f"--build-method={build_method}"]
    commit_hash = os.getenv("GITHUB_SHA")
    git_url = f"{os.getenv('GITHUB_SERVER_URL')}/{os.getenv('GITHUB_REPOSITORY')}/tree/{commit_hash}"
    if deployment_name:
        deployment_flag = [f"--deployment={deployment_name}"]
    else:
        deployment_flag = []
    return run(
        [
            str(DAGSTER_CLOUD_PEX_PATH),
            "-m",
            "dagster_cloud_cli.entrypoint",
            "serverless",
            "deploy-python-executable",
            *args,
            f"--location-name=*",
            f"--location-file={dagster_cloud_yaml}",
            f"--git-url={git_url}",
            f"--commit-hash={commit_hash}",
        ]
        + deployment_flag
    )


if __name__ == "__main__":
    main()
