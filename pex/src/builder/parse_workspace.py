from dataclasses import dataclass
import os
from typing import Dict, List
import yaml


@dataclass
class Location:
    name: str
    directory: str
    build_folder: str
    location_file: str


def get_locations(dagster_cloud_yaml_file) -> List[Location]:
    """Returns list of locations parsed from dagster_cloud.yaml."""
    base_dir = os.path.abspath(os.path.dirname(dagster_cloud_yaml_file))

    def abs_path(directory):
        return os.path.join(base_dir, directory)

    with open(dagster_cloud_yaml_file) as yaml_file:
        workspace_contents = yaml_file.read()
        workspace_contents_yaml = yaml.safe_load(workspace_contents)

        locations = []
        for location in workspace_contents_yaml["locations"]:
            location_dir = os.path.join(
                base_dir, location.get("build", {"directory": "."}).get("directory")
            )
            locations.append(
                Location(
                    name=location["location_name"],
                    directory=location_dir,
                    build_folder=location_dir,
                    location_file=os.path.abspath(dagster_cloud_yaml_file),
                )
            )
        return locations
