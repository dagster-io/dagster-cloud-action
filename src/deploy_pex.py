#!/usr/bin/env python

# Switches PEX deploy behavior based on github runner's ubuntu version
# ubuntu-20.04 can always build pexes that work on our target platform
# ubuntu-22.04 can only build pexes if there are no sdists (source only packages)

# On ubuntu-20.04: forward args to builder.pex

# On ubuntu-22.04:
#   Try to build without sdists
#     If success: all good (no sdists were involved)
#     If failure: run builder.pex within the dagster-manylinux-builder docker image

import os
from pathlib import Path
import subprocess
import sys

BUILDER_PEX_PATH = Path(__file__).parent.parent / "generated/gha/builder.pex"
DOCKER_PATH = "/usr/bin/docker"
DOCKER_IMAGE = "ghcr.io/dagster-io/dagster-manylinux-builder:v0.1"


def main():
    args = sys.argv[1:]

    if get_runner_ubuntu_version() == "20.04":
        returncode, output = deploy_pex_from_current_environment(args, build_sdists=True)
    else:
        returncode, output = deploy_pex_from_current_environment(args, build_sdists=False)
        if returncode:
            dep_failures = dependency_failure_lines(output)
            if dep_failures:
                try:
                    print(
                        "::group::Preparing a Docker build environment to build the PEX files",
                        flush=True,
                    )
                    print(
                        "Going to build dependencies within a Docker build environment "
                        "to resolve missing binary packages for the following:"
                    )
                    for line in dep_failures:
                        print(f"- {line}")

                    returncode, output = deploy_pex_from_docker(args)
                finally:
                    print("::endgroup::", flush=True)

            if returncode:
                print(
                    "::error Title=Deploy failed::Failed to deploy Python Executable. "
                    "Try removing `ENABLE_FAST_DEPLOYS: 'true'` from your .github/workflows/*yml."
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


def dependency_failure_lines(lines):
    return [line for line in lines if "No matching distribution" in line]


def deploy_pex_from_current_environment(args, build_sdists: bool):
    if build_sdists:
        args = args + ["--build-sdists"]
    else:
        args = args + ["--no-build-sdists"]

    return run(
        [
            str(BUILDER_PEX_PATH),
            *args,
        ]
    )


def deploy_pex_from_docker(args):
    # This invokes the docker cli.
    # The problem with using the a Github custom docker action instead is that the docker image
    # is always downloaded (even if it is a conditional step that is never run). Using the CLI
    # makes the download lazy (takes about 40 seconds). But requires a bunch of directory and
    # env mappings. These have been copied from an actual Github docker action.
    local_github_workspace_path = os.environ["GITHUB_WORKSPACE"]
    github_docker_envs = [
        "GITHUB_WORKSPACE=/github/workspace",
        "GITHUB_EVENT_PATH=/github/workflow/event.json",
        "GITHUB_WORKFLOW",
        "DAGSTER_CLOUD_URL",
        "DAGSTER_CLOUD_API_TOKEN",
        "ENABLE_FAST_DEPLOYS",
        "ACTION_REPO",
        "FLAG_DEPS_CACHE_FROM",
        "FLAG_DEPS_CACHE_TO",
        "pythonLocation",
        "LD_LIBRARY_PATH",
        "GITHUB_TOKEN",
        "HOME=/github/home",
        "GITHUB_JOB",
        "GITHUB_REF",
        "GITHUB_SHA",
        "GITHUB_REPOSITORY",
        "GITHUB_REPOSITORY_OWNER",
        "GITHUB_RUN_ID",
        "GITHUB_RUN_NUMBER",
        "GITHUB_RETENTION_DAYS",
        "GITHUB_RUN_ATTEMPT",
        "GITHUB_ACTOR",
        "GITHUB_TRIGGERING_ACTOR",
        "GITHUB_HEAD_REF",
        "GITHUB_BASE_REF",
        "GITHUB_EVENT_NAME",
        "GITHUB_SERVER_URL",
        "GITHUB_API_URL",
        "GITHUB_GRAPHQL_URL",
        "GITHUB_REF_NAME",
        "GITHUB_REF_PROTECTED",
        "GITHUB_REF_TYPE",
        "GITHUB_ACTION",
        "GITHUB_ACTION_REPOSITORY",
        "GITHUB_ACTION_REF",
        "GITHUB_PATH",
        "GITHUB_ENV",
        "GITHUB_STEP_SUMMARY",
        "GITHUB_STATE",
        "GITHUB_OUTPUT",
        "GITHUB_ACTION_PATH",
        "RUNNER_OS",
        "RUNNER_ARCH",
        "RUNNER_NAME",
        "RUNNER_TOOL_CACHE",
        "RUNNER_TEMP",
        "RUNNER_WORKSPACE",
        "ACTIONS_RUNTIME_URL",
        "ACTIONS_RUNTIME_TOKEN",
        "ACTIONS_CACHE_URL",
        "GITHUB_ACTIONS=true",
        "CI=true",
    ]
    github_docker_mounts = [
        f"{local_github_workspace_path}:/github/workspace",
        "/home/runner/work/_temp/_github_workflow:/github/workflow",
        "/var/run/docker.sock:/var/run/docker.sock",
        "/home/runner/work/_temp/_github_home:/github/home",
        "/home/runner/work/_temp/_runner_file_commands:/github/file_commands",
    ]

    docker_run_args = [
        "--workdir",
        "/github/workspace",
        "--rm",
        "--entrypoint",
        "/usr/bin/bash",
    ]
    for env in github_docker_envs:
        docker_run_args.extend(["-e", env])
    for mnt in github_docker_mounts:
        docker_run_args.extend(["-v", mnt])
    builder_pex_args = " ".join(args) + " --build-sdists"
    # map local paths to mounted paths
    builder_pex_args = builder_pex_args.replace(local_github_workspace_path, "/github/workspace")
    docker_run_args.extend(
        [
            "ghcr.io/dagster-io/dagster-manylinux-builder:dev",
            "-c",
            f"git config --global --add safe.directory /github/workspace/project-repo; /builder.pex {builder_pex_args}",
        ]
    )
    return run(["/usr/bin/docker", "run", *docker_run_args])


if __name__ == "__main__":
    main()
