# end-to-end workflow for rebuilding and publishing code locations

from dataclasses import dataclass
import dataclasses
import logging
import pprint
import sys
from typing import Dict, Iterable, List, Optional
from . import parse_workspace, deps, registry_info, source, util


@dataclass
class LocationBuild:
    "Inputs and outputs for each code location"
    location: parse_workspace.Location
    deps_requirements: deps.DepsRequirements

    # One of deps_pex_path or published_deps_pex should be set
    deps_pex_path: Optional[str] = None  # locally build deps.pex
    published_deps_pex: Optional[str] = None  # already published deps.pex

    source_pex_path: Optional[str] = None
    pex_tag: Optional[str] = None  # composite tag used to identify the set of pex files


def deploy_project(dagster_cloud_yaml_file: str, output_directory: str):
    """Rebuild and publish code locations in a project."""

    registry_info.get_registry_info()

    locations = parse_workspace.get_locations(dagster_cloud_yaml_file)

    location_builds = build_locations(locations, output_directory)

    print(f"Built locations ({len(location_builds)}):")
    for build in location_builds:
        pprint.pprint(dataclasses.asdict(build))


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

    # build each deps pex once and assign to all related builds
    for requirements_hash in builds_for_requirements_hash:
        builds = builds_for_requirements_hash[requirements_hash]
        deps_requirements = builds[0].deps_requirements

        # don't build deps.pex files that are already published
        published_deps_pex = get_published_deps_pex_name(deps_requirements.hash)

        if published_deps_pex:
            logging.info(
                "Found published deps.pex %r for requirements_hash %r",
                published_deps_pex,
                deps_requirements.hash,
            )
            for location_build in builds:
                location_build.published_deps_pex = published_deps_pex
        else:
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

    # compute pex tags
    for location_build in location_builds:
        deps_pex = (
            location_build.deps_pex_path
            if location_build.deps_pex_path
            else location_build.published_deps_pex
        )
        if not deps_pex or not location_build.source_pex_path:
            raise ValueError("No deps.pex or source.pex")

        location_build.pex_tag = util.build_pex_tag(
            [deps_pex, location_build.source_pex_path]
        )
    return location_builds


def get_published_deps_pex_name(requirements_hash: str) -> Optional[str]:
    # TODO: read registry and return name of deps pex file already built for given
    # requirements_hash
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    deploy_project(sys.argv[1], sys.argv[2])
