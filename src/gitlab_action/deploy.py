#!/usr/bin/env python

import os
import subprocess
import sys

import parse_workspace


def deploy(dagster_cloud_yaml_file):
    if not os.getenv("SERVERLESS_BASE_IMAGE_PREFIX"):
        base_image_prefix = "657821118200.dkr.ecr.us-west-2.amazonaws.com/dagster-cloud-serverless-base-"
        if ".dogfood." in os.environ["DAGSTER_CLOUD_URL"]:
            base_image_prefix = "878483074102.dkr.ecr.us-west-2.amazonaws.com/dagster-cloud-serverless-base-"
        os.environ["SERVERLESS_BASE_IMAGE_PREFIX"] = base_image_prefix

    project = os.getenv("CI_PROJECT_NAME")
    project_url = os.getenv("CI_PROJECT_URL")
    commit = os.getenv("CI_COMMIT_SHORT_SHA")
    branch = os.getenv("CI_COMMIT_BRANCH")

    deps_cache = project + "/" + branch
    commit_url = project_url + "/commit/" + commit

    locations = parse_workspace.get_locations(dagster_cloud_yaml_file)
    for location in locations:
        try:
            if os.getenv("DISABLE_FAST_DEPLOYS"):
                legacy_deploy(location.name, dagster_cloud_yaml_file, commit, commit_url)
            else:
                fast_deploy(
                    location_name=location.name,
                    location_file=dagster_cloud_yaml_file,
                    deps_cache=deps_cache,
                    commit=commit,
                    url=commit_url,
                )
        except subprocess.CalledProcessError as err:
            print("Failed to update code location", location.name)
            print(err.output)
            sys.exit(1)


def fast_deploy(location_name, location_file, deps_cache, commit, url):
    print("Updating code location", location_name)
    subprocess.check_call(
        [
            "dagster-cloud",
            "serverless",
            "deploy-python-executable",
            f"--location-name={location_name}",
            f"--location-file={location_file}",
            f"--deps-cache-from={deps_cache}",
            "--deps-cache-to={deps_cache}",
            f"--commit-hash={commit}",
            f"--git-url={url}",
        ],
        stderr=subprocess.STDOUT,
    )

def legacy_deploy(location_name, location_file, commit, url):
    print("skip")


if __name__ == "__main__":
    dagster_cloud_yaml_file = sys.argv[1]
    if os.path.exists(dagster_cloud_yaml_file):
        deploy(dagster_cloud_yaml_file)
    else:
        print("Not found", dagster_cloud_yaml_file)
        sys.exit(1)
