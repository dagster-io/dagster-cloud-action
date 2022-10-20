# end-to-end workflow for rebuilding and publishing code locations

import dataclasses
import logging
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import click

from . import (code_location, deps, github_context, parse_workspace,
               pex_registry, source, util)

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
    dagster_cloud_yaml_file: str, output_directory: str, python_version: Tuple[str, str]
) -> List[LocationBuild]:
    """Rebuild pexes for code locations in a project."""

    locations = parse_workspace.get_locations(dagster_cloud_yaml_file)

    location_builds = build_locations(locations, output_directory, python_version)

    logging.info(f"Built locations (%s):", len(location_builds))
    for build in location_builds:
        logging.info(str(dataclasses.asdict(build)))

    return location_builds


def build_locations(
    locations: List[parse_workspace.Location],
    output_directory: str,
    python_version: Tuple[str, str],
) -> List[LocationBuild]:
    location_builds = [
        LocationBuild(
            location=location,
            deps_requirements=deps.get_deps_requirements(
                location.directory, python_version=python_version
            ),
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
                deps_requirements, output_directory, python_version
            )

            for location_build in builds:
                location_build.deps_pex_path = deps_pex_path

    # build each source once
    for location_build in location_builds:
        location_build.source_pex_path = source.build_source_pex(
            location_build.location.directory, output_directory, python_version
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
    ctx = click.get_current_context()
    if ctx.params["upload_pex"]:
        return pex_registry.get_deps_pex_name_from_requirements_hash(requirements_hash)
    return None


@click.command()
@click.argument("dagster_cloud_file", type=click.Path(exists=True))
@click.argument("build_output_dir", type=click.Path(exists=False))
@click.option(
    "--upload-pex",
    is_flag=True,
    show_default=True,
    default=False,
    help="Upload PEX files to registry.",
)
@click.option(
    "--update-code-location",
    is_flag=True,
    show_default=True,
    default=False,
    help="Update code location to use new PEX files.",
)
@util.python_version_option()
def deploy_main(
    dagster_cloud_file,
    build_output_dir,
    upload_pex,
    update_code_location,
    python_version,
):
    # always build
    with github_context.log_group("Building PEX Files"):
        location_builds = build_project(
            dagster_cloud_file,
            build_output_dir,
            python_version=tuple(python_version.split(".")),
        )

    # upload to registry if enabled
    if upload_pex:
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
        logging.info("Skipping upload to pex registry: no --upload-pex")

    # update code location if enabled
    if update_code_location:
        deployment = "prod"  # default

        github_event = github_context.github_event(os.path.dirname(dagster_cloud_file))
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
                    location_file=dagster_cloud_file,
                    commit_hash=github_event.github_sha,
                )

        code_location.wait_for_load(
            deployment_name=deployment,
            location_names=[
                location_build.location.name for location_build in location_builds
            ],
        )
    else:
        logging.info("Skipping code location update: no --update-code-location")

    logging.info("All done")


if __name__ == "__main__":
    deploy_main()
