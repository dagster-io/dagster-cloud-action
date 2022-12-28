#!/usr/bin/env python
import os
from pathlib import Path
import subprocess
import sys

BUILDER_PEX_PATH = Path(__file__).parent.parent / "generated/gha/builder.pex"
DOCKER_PATH = "/usr/bin/docker"
DOCKER_IMAGE = "ghcr.io/dagster-io/dagster-manylinux-builder:dev"


def main():
    args = sys.argv[1:]

    returncode, output = deploy_pex_from_current_environment(args)
    if returncode:
        dep_failures = dependency_failure_lines(output)
        if dep_failures:
            print("Failed to find binary packages for the following:")
            for line in dep_failures:
                print(f"- {line}")
            print(
                "Will rebuild the Python Executable within Docker to build source only packages (sdists)."
            )
            returncode, output = deploy_pex_from_docker(args)


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


def deploy_pex_from_current_environment(args):
    return run(
        [
            BUILDER_PEX_PATH,
            *args,
        ]
    )


def deploy_pex_from_docker(args):
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
    builder_pex_args = builder_pex_args.replace(
        local_github_workspace_path, "/github/workspace"
    )
    docker_run_args.extend(
        [
            "ghcr.io/dagster-io/dagster-manylinux-builder:dev",
            "-c",
            f"git config --global --add safe.directory /github/workspace/project-repo; /builder.pex {builder_pex_args}",
        ]
    )
    return run(["/usr/bin/docker", "run", *docker_run_args])


def fallback_to_docker_deploy():
    import yaml, json
    import os

    workspace = os.path.join(
        os.environ["GITHUB_WORKSPACE"], "project-repo/dagster_cloud.yaml"
    )
    secrets_set = bool(os.getenv("DAGSTER_CLOUD_API_TOKEN"))

    with open(workspace) as f:
        workspace_contents = f.read()
    workspace_contents_yaml = yaml.safe_load(workspace_contents)

    output_obj = [
        {
            "name": location["location_name"],
            "directory": location.get("build", {"directory": "."}).get("directory"),
            "build_folder": location.get("build", {"directory": "."}).get("directory"),
            "registry": location.get("build", {"directory": "."}).get("registry"),
            "location_file": str(workspace),
        }
        for location in workspace_contents_yaml["locations"]
    ]
    print(f"set-output name=build_info::{json.dumps(output_obj)}")
    print(f"set-output name=secrets_set::{json.dumps(secrets_set)}")


if __name__ == "__main__":
    fallback_to_docker_deploy()
    # main()
