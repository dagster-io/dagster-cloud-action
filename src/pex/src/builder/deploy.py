# end-to-end workflow for rebuilding and publishing code locations

from dataclasses import dataclass
import dataclasses
import logging
import os
import sys
from typing import Dict, List, Optional
from . import (
    parse_workspace,
    deps,
    source,
    util,
    code_location,
    github_context,
    pex_registry,
)

PEX_BASE_IMAGE = "878483074102.dkr.ecr.us-west-2.amazonaws.com/dagster-cloud-agent-pre-license:pexdemo"


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
                "Found published deps.pex %r for requirements_hash %r, skipping rebuild.",
                published_deps_pex,
                deps_requirements.hash,
            )

            for location_build in builds:
                location_build.published_deps_pex = published_deps_pex
        else:
            logging.info(
                "No published deps.pex found for requirements_hash %r, will rebuild.",
                deps_requirements.hash,
            )
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
    if PEX_REGISTRY_ENABLED:
        return pex_registry.get_deps_pex_name_from_requirements_hash(requirements_hash)
    return None


if __name__ == "__main__":
    # TODO: use a real command line parser
    dagster_cloud_file_path, build_output_dir = sys.argv[1:3]
    flags = set(sys.argv[3:])  # '--deploy', '--enable-pex-registry'

    # whether to upload built files to the pex registry
    PEX_REGISTRY_ENABLED = "--enable-pex-registry" in flags

    # where to update dagster cloud code location with pex tag
    SHOULD_DEPLOY = "--deploy" in flags

    # always build
    with github_context.log_group("Building PEX Files"):
        location_builds = build_project(dagster_cloud_file_path, build_output_dir)

    # upload to registry if enabled
    if PEX_REGISTRY_ENABLED:
        with github_context.log_group("Uploading PEX Files"):
            for location_build in location_builds:
                paths = [
                    filepath
                    for filepath in [
                        location_build.source_pex_path,
                        location_build.deps_pex_path,
                    ]
                    if filepath is not None
                ]
                if not paths:
                    logging.error("No built files for %s", location_build.location.name)
                pex_registry.upload_files(paths)
                if location_build.deps_pex_path:
                    # if the deps.pex was built, set or update the requirements hash value
                    pex_registry.set_requirements_hash_values(
                        location_build.deps_requirements.hash,
                        os.path.basename(location_build.deps_pex_path),
                    )
    else:
        logging.info("Skipping upload to pex registry: no --enable-pex-registry")

    # update code location if enabled
    if SHOULD_DEPLOY:
        deployment = "prod"  # default

        github_event = github_context.github_event(
            os.path.dirname(dagster_cloud_file_path)
        )
        if github_event.branch_name:
            with github_context.log_group("Updating Branch Deployment"):
                logging.info(
                    "Creating/updating branch deployment for %r",
                    github_event.branch_name,
                )
                deployment = code_location.create_or_update_branch_deployment_from_github_context(
                    github_event
                )
                if not deployment:
                    raise ValueError("Could not create branch deployment", github_event)

        for location_build in location_builds:
            location_name = location_build.location.name
            with github_context.log_group(f"Updating code location: {location_name}"):
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

        code_location.wait_for_load(
            deployment_name=deployment,
            location_names=[
                location_build.location.name for location_build in location_builds
            ],
        )

    # TODO: wait for dagster cloud to apply location updates

    logging.info("All done")