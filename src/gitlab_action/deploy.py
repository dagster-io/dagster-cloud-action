#!/usr/bin/env python

import os
import subprocess
import sys

import parse_workspace


def deploy(dagster_cloud_yaml_file, deployment=None):
    url = os.environ["DAGSTER_CLOUD_URL"]
    if not os.getenv("SERVERLESS_BASE_IMAGE_PREFIX"):
        base_image_prefix = "657821118200.dkr.ecr.us-west-2.amazonaws.com/dagster-cloud-serverless-base-"
        if ".dogfood." in url:
            base_image_prefix = "878483074102.dkr.ecr.us-west-2.amazonaws.com/dagster-cloud-serverless-base-"
        os.environ["SERVERLESS_BASE_IMAGE_PREFIX"] = base_image_prefix

    project = os.getenv("CI_PROJECT_NAME")
    project_url = os.getenv("CI_PROJECT_URL")
    commit = os.getenv("CI_COMMIT_SHORT_SHA")
    branch = os.getenv("CI_COMMIT_BRANCH") or os.getenv("CI_COMMIT_REF_NAME")
    python_version = os.getenv("PYTHON_VERSION")

    deps_cache = project + "/" + branch
    commit_url = project_url + "/commit/" + commit

    locations = parse_workspace.get_locations(dagster_cloud_yaml_file)
    assert not os.getenv("DISABLE_FAST_DEPLOYS")

    for location in locations:
        try:
            print("Updating code location", location.name)
            command_args = [
                "dagster-cloud",
                "serverless",
                "deploy-python-executable",
                f"--location-name={location.name}",
                f"--location-file={location.location_file}",
                f"--deps-cache-from={deps_cache}",
                f"--deps-cache-to={deps_cache}",
                f"--commit-hash={commit}",
                f"--git-url={commit_url}",
                f"--python-version={python_version}"
            ]
            if deployment:
                command_args.append(f"--url={url}/{deployment}")
            if location.build_folder:
                command_args.append(location.build_folder)
            subprocess.check_call(command_args, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as err:
            print("Failed to update code location", location.name)
            print(err.output)
            sys.exit(1)


if __name__ == "__main__":
    dagster_cloud_yaml_file = sys.argv[1]
    deployment = sys.argv[2] if len(sys.argv) > 2 else None
    if os.path.exists(dagster_cloud_yaml_file):
        deploy(dagster_cloud_yaml_file, deployment)
    else:
        print("Could not find dagster_cloud.yaml", dagster_cloud_yaml_file)
        sys.exit(1)
