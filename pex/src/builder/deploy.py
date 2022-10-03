# end-to-end workflow for rebuilding and publishing code locations

from dataclasses import dataclass
import sys
from typing import Dict, List, Optional
from . import parse_workspace, deps, source


@dataclass
class LocationBuild:
    "Inputs and outputs for each code location"
    location: parse_workspace.Location
    deps_requirements: deps.DepsRequirements
    deps_pex_path: Optional[str] = None
    source_pex_path: Optional[str] = None


def deploy_project(dagster_cloud_yaml_file: str, output_directory: str):
    """Rebuild and publish code locations in a project."""

    locations = parse_workspace.get_locations(dagster_cloud_yaml_file)

    location_builds = build_locations(locations, output_directory)

    print("Built locations:", location_builds)


def build_locations(
    locations: List[parse_workspace.Location], output_directory: str
) -> List[LocationBuild]:
    location_builds = [
        LocationBuild(
            location=location,
            deps_requirements=deps.get_deps_requirements(location.directory),
        )
        for location in locations
    ]

    # dedup requirements so each is only built once
    builds_for_requirements_hash: Dict[str, List[LocationBuild]] = {}
    for location_build in location_builds:
        requirements_hash = location_build.deps_requirements.hash
        builds_for_requirements_hash.setdefault(requirements_hash, []).append(
            location_build
        )

    # TODO: prune all_deps_requirements to only build unpublished deps

    # build each deps pex once and assign to all related builds
    for requirements_hash in builds_for_requirements_hash:
        builds = builds_for_requirements_hash[requirements_hash]
        deps_requirements = builds[0].deps_requirements
        deps_pex_path = deps.build_deps_from_requirements(
            deps_requirements, output_directory
        )

        for location_build in builds:
            location_build.deps_pex_path = deps_pex_path

    # build each source once
    for location_build in location_builds:
        location_build.source_pex_path = source.build_source_pex(
            location_build.location.directory, output_directory
        )

    return location_builds


if __name__ == "__main__":
    deploy_project(sys.argv[1], sys.argv[2])
