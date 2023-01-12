import json
import os
import sys
from dataclasses import asdict, dataclass
from typing import List

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

    with open(dagster_cloud_yaml_file, encoding="utf-8") as yaml_file:
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


if __name__ == "__main__":
    filename = sys.argv[1]
    locations = get_locations(filename)
    location_names = [location.name for location in locations]
    locations_by_name = { location.name: location for location in locations }
    location_arg = sys.argv[2] if len(sys.argv) >= 3 else locations[0].name
    location = locations_by_name.get(location_arg)
    location_json = json.dumps(asdict(location))
    print(f'DAGSTER_CLOUD_LOCATION={location_json}')
    print(f'DAGSTER_CLOUD_LOCATION_NAME={location.name}')
    print(f'DAGSTER_CLOUD_LOCATION_DIR={location.build_folder}')