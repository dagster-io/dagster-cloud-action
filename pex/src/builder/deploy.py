# end-to-end workflow for rebuilding and publishing code locations

from dataclasses import dataclass
import dataclasses
import logging
import pprint
import sys
from typing import Dict, List, Optional
from . import (
    parse_workspace,
    deps,
    registry_info,
    source,
    util,
    code_location,
    github_context,
)

PEX_BASE_IMAGE = ":pex_base_image"


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


def build_project(
    dagster_cloud_yaml_file: str, output_directory: str
) -> List[LocationBuild]:
    """Rebuild pexes for code locations in a project."""

    registry_info.get_registry_info()

    locations = parse_workspace.get_locations(dagster_cloud_yaml_file)

    location_builds = build_locations(locations, output_directory)

    logging.info(f"Built locations (%s):", len(location_builds))
    for build in location_builds:
        logging.info(str(dataclasses.asdict(build)))

    return location_builds


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
    # TODO: read s3 registry and return name of deps pex file already built for given
    # requirements_hash
    return None


if __name__ == "__main__":
    # TODO: use a real command line parser
    dagster_cloud_file_path, build_output_dir = sys.argv[1:3]
    flags = set(sys.argv[3:])

    location_builds = build_project(dagster_cloud_file_path, build_output_dir)

    if "--deploy" in flags:
        github_event = github_context.github_event()
        deployment = "prod"  # default

        if github_event.branch_name:
            logging.info(
                "Creating/updating branch deployment for %r", github_event.branch_name
            )
            deployment = (
                code_location.create_or_update_branch_deployment_from_github_context(
                    github_event
                )
            )

        for location_build in location_builds:
            location_name = location_build.location.name
            logging.info(
                "Updating code location %r for deployment %r with pex_tag %r",
                location_name,
                deployment,
                location_build.pex_tag,
            )
            code_location.add_or_update_code_location(
                deployment,
                location_name,
                image=PEX_BASE_IMAGE,
                pex_tag=location_build.pex_tag,
                location_file=dagster_cloud_file_path,
                commit_hash=github_event.github_sha,
            )

        logging.info("Done updating code locations.")

        # TODO: wait for dagster cloud to apply location updates
