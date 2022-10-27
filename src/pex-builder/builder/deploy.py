# end-to-end workflow for rebuilding and publishing code locations

import dataclasses
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import click
from packaging import version

from . import (
    code_location,
    deps,
    github_context,
    parse_workspace,
    pex_registry,
    source,
    util,
)


@dataclass
class LocationBuild:
    "Inputs and outputs for each code location"
    location: parse_workspace.Location
    deps_requirements: deps.DepsRequirements

    # One of deps_pex_path or published_deps_pex should be set
    deps_pex_path: Optional[str] = None  # locally build deps.pex
    published_deps_pex: Optional[str] = None  # already published deps.pex
    # dagster_version should be always set for both cases, pre published and locally built deps
    dagster_version: Optional[str] = None
    source_pex_path: Optional[str] = None
    pex_tag: Optional[str] = None  # composite tag used to identify the set of pex files


def build_project(
    dagster_cloud_yaml_file: str,
    output_directory: str,
    upload_pex: bool,
    deps_cache_tag: Optional[str],
    python_version: version.Version,
) -> List[LocationBuild]:
    """Rebuild pexes for code locations in a project."""

    locations = parse_workspace.get_locations(dagster_cloud_yaml_file)

    location_builds = build_locations(
        locations, output_directory, upload_pex, deps_cache_tag, python_version
    )

    logging.info(f"Built locations (%s):", len(location_builds))
    for build in location_builds:
        logging.info(str(dataclasses.asdict(build)))

    return location_builds


def build_locations(
    locations: List[parse_workspace.Location],
    output_directory: str,
    upload_pex: bool,
    deps_cache_tag: Optional[str],
    python_version: version.Version,
) -> List[LocationBuild]:
    location_builds = [
        LocationBuild(
            location=location,
            deps_requirements=deps.get_deps_requirements(
                location.directory,
                python_version=python_version,
                cache_tag=deps_cache_tag,
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

        # if a cache_tag is specified, don't build deps.pex files that are already published
        if upload_pex and deps_requirements.cache_tag:
            published_deps_pex_info = pex_registry.get_requirements_hash_values(deps_requirements.hash)
        else:
            published_deps_pex_info = None

        if published_deps_pex_info:
            published_deps_pex = published_deps_pex_info["deps_pex_name"]
            logging.info(
                "Found published deps.pex %r for requirements_hash %r, skipping rebuild.",
                published_deps_pex,
                deps_requirements.hash,
            )

            for location_build in builds:
                location_build.published_deps_pex = published_deps_pex
                location_build.dagster_version = published_deps_pex_info[
                    "dagster_version"
                ]
        else:
            logging.info(
                "No published deps.pex found for requirements_hash %r, will rebuild.",
                deps_requirements.hash,
            )
            deps_pex_path, dagster_version = deps.build_deps_from_requirements(
                deps_requirements, output_directory
            )

            for location_build in builds:
                location_build.deps_pex_path = deps_pex_path
                location_build.dagster_version = dagster_version

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


def get_base_image_for(location_build: LocationBuild):
    python_version = location_build.deps_requirements.python_version
    dagster_version = location_build.dagster_version
    py_tag = f"py{python_version.major}.{python_version.minor}"  # eg 'py3.8'
    # TODO: verify this image exists in the registry
    return (
        f"ghcr.io/dagster-io/dagster-cloud-serverless-base-{py_tag}:{dagster_version}"
    )


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
    "--deps-cache-tag",
    type=str,
    required=False,
    help="Enables caching for the deps pex file, "
    "using this tag in addition to the requirements list as the cache key",
)
@click.option(
    "--update-code-location",
    is_flag=True,
    show_default=True,
    default=False,
    help="Update code location to use new PEX files.",
)
@util.python_version_option()
def cli(
    dagster_cloud_file,
    build_output_dir,
    upload_pex,
    deps_cache_tag,
    update_code_location,
    python_version,
):
    deploy_main(
        dagster_cloud_file,
        build_output_dir,
        upload_pex,
        deps_cache_tag,
        update_code_location,
        python_version,
    )


def deploy_main(
    dagster_cloud_file: str,
    build_output_dir: str,
    upload_pex: bool,
    deps_cache_tag: Optional[str],
    update_code_location: bool,
    python_version: str,
):
    # always build
    with github_context.log_group("Building PEX Files"):
        location_builds = build_project(
            dagster_cloud_file,
            build_output_dir,
            upload_pex=upload_pex,
            deps_cache_tag=deps_cache_tag,
            python_version=util.parse_python_version(python_version),
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
                        dagster_version=location_build.dagster_version,
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
                base_image = os.getenv("CUSTOM_BASE_IMAGE")
                if not base_image:
                    base_image = get_base_image_for(location_build)
                code_location.add_or_update_code_location(
                    deployment,
                    location_name,
                    image=base_image,
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

    return location_builds


if __name__ == "__main__":
    cli()
