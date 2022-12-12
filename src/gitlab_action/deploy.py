#!/usr/bin/env python

import os
import subprocess
import sys

import parse_workspace


def deploy(dagster_cloud_yaml_file):
    if not os.getenv('SERVERLESS_BASE_IMAGE_PREFIX'):
        base_image_prefix = "657821118200.dkr.ecr.us-west-2.amazonaws.com/dagster-cloud-serverless-base-"
        if '.dogfood.' in os.environ['DAGSTER_CLOUD_URL']:
            base_image_prefix =  "878483074102.dkr.ecr.us-west-2.amazonaws.com/dagster-cloud-serverless-base-"
        os.environ['SERVERLESS_BASE_IMAGE_PREFIX'] = base_image_prefix

    locations = parse_workspace.get_locations(dagster_cloud_yaml_file)
    for location in locations:
        try:
            print("Updating code location", location.name)
            subprocess.check_call(
                [
                    "dagster-cloud",
                    "workspace",
                    "update-location",
                    f"--upload-python-executable={location.build_folder}",
                    f"--location-name={location.name}",
                    f"--location-file={dagster_cloud_yaml_file}",
                    "--deps-cache-from=gitlab",
                    "--deps-cache-to=gitlab",
                    f"--commit-hash={os.getenv('CI_COMMIT_SHORT_SHA')}",
                    f"--git-url={os.getenv('CI_PROJECT_URL')}",
                ],
                stderr=subprocess.STDOUT
            )
        except subprocess.CalledProcessError as err:
            print("Failed to update code location", location.name)
            print(err.output)
            sys.exit(1)


if __name__ == '__main__':
    dagster_cloud_yaml_file = sys.argv[1]
    if os.path.exists(dagster_cloud_yaml_file):
        deploy(dagster_cloud_yaml_file)
    else:
        print("Not found", dagster_cloud_yaml_file)
        sys.exit(1)
