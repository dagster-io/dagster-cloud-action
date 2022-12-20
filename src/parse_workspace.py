import sys
import yaml
import json
import os


def parse_workspace(dagster_cloud_file):
    workspace = dagster_cloud_file
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
    print(f"::set-output name=build_info::{json.dumps(output_obj)}")
    print(f"::set-output name=secrets_set::{json.dumps(secrets_set)}")


if __name__ == "__main__":
    dagster_cloud_yaml_file = sys.argv[1]
    parse_workspace(dagster_cloud_yaml_file)
