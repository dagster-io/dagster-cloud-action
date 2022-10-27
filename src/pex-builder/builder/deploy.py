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


@dataclass
class DepsCacheTags:
    deps_cache_tag_read: Optional[str]
    deps_cache_tag_write: Optional[str]


def build_project(
    dagster_cloud_yaml_file: str,
    output_directory: str,
    upload_pex: bool,
    deps_cache_tags: DepsCacheTags,
    python_version: version.Version,
) -> List[LocationBuild]:
    """Rebuild pexes for code locations in a project."""

    locations = parse_workspace.get_locations(dagster_cloud_yaml_file)

    location_builds = build_locations(
        locations, output_directory, upload_pex, deps_cache_tags, python_version
    )

    logging.info(f"Built locations (%s):", len(location_builds))
    for build in location_builds:
        logging.info(str(dataclasses.asdict(build)))

    return location_builds


def build_locations(
    locations: List[parse_workspace.Location],
    output_directory: str,
    upload_pex: bool,
    deps_cache_tags: DepsCacheTags,
    python_version: version.Version,
) -> List[LocationBuild]:
    location_builds = [
        LocationBuild(
            location=location,
            deps_requirements=deps.get_deps_requirements(
                location.directory,
                python_version=python_version,
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

        # if a read cache_tag is specified, don't build deps.pex files if it is already published
        if upload_pex and deps_cache_tags.deps_cache_tag_read:
            published_deps_pex_info = pex_registry.get_cached_deps_details(
                deps_requirements.hash, deps_cache_tags.deps_cache_tag_read
            )
        else:
            published_deps_pex_info = None

        if published_deps_pex_info:
            published_deps_pex = published_deps_pex_info["deps_pex_name"]
            logging.info(
                "Found published deps.pex %r for requirements_hash %r, cache_tag %r, "
                "skipping rebuild.",
                published_deps_pex,
                deps_requirements.hash,
                deps_cache_tags.deps_cache_tag_read,
            )

            for location_build in builds:
                location_build.published_deps_pex = published_deps_pex
                location_build.dagster_version = published_deps_pex_info[
                    "dagster_version"
                ]
        else:
            logging.info(
                "No published deps.pex found for requirements_hash %r, cache_tag %r, will rebuild.",
                deps_requirements.hash,
                deps_cache_tags.deps_cache_tag_read,
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
    "--deps-cache-tag-read",
    type=str,
    required=False,
    help="The cache_tag to read for the deps pex file. See summary for details.",
)
@click.option(
    "--deps-cache-tag-write",
    type=str,
    required=False,
    help="The cache_tag to write for the deps pex file. See summary for details.",
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
    deps_cache_tag_write,
    deps_cache_tag_read,
    update_code_location,
    python_version,
):
    """Build and deploy a code location based on PEX files.

    Examples:

    To build the code locally but not upload the code:
    $ builder.pex deploy path/to/dagster_cloud.yaml path/to/build_output

    To build and upload the code, but not update the code location:
    $ builder.pex deploy --upload-pex path/to/dagster_cloud.yaml path/to/build_output

    To build, upload the code, and update the code location:
    $ builder.pex deploy --upload-pex --update-code-location path/to/dagster_cloud.yaml path/to/build_output

    The built code contains two files - source-HASH.pex and deps-HASH.pex. The deps-HASH.pex can be
    reused if previously uploaded and the requirements.txt or setup.py did not change.

    To build the deps-HASH.pex once and reuse, specify the same value in both read and write tags:
    $ builder.pex deploy ... --deps-cache-tag-read=main --deps-cache-tag-write=main ...

    To force a rebuild for a specific cache tag, specify only the write tag but not the read tag:
    $ builder.pex deploy ... --deps-cache-tag-write=main ...

    To seed a new cache tag from an existing cache tag, specify the source tag as the read tag:
    $ builder.pex deploy ... --deps-cache-tag-read=main --deps-cache-tag-write=branch1 ...

    If the content of requirements.txt or setup.py changes, the read tag has no effect and
    deps-HASH.pex is always rebuilt.
    """
    deploy_main(
        dagster_cloud_file,
        build_output_dir,
        upload_pex=upload_pex,
        deps_cache_tag_read=deps_cache_tag_read,
        deps_cache_tag_write=deps_cache_tag_write,
        update_code_location=update_code_location,
        python_version=python_version,
    )


def deploy_main(
    dagster_cloud_file: str,
    build_output_dir: str,
    *,
    upload_pex: bool,
    deps_cache_tag_read: Optional[str],
    deps_cache_tag_write: Optional[str],
    update_code_location: bool,
    python_version: str,
):
    # We don't have strict checking, but print warnings in case flags don't make sense
    if deps_cache_tag_read or deps_cache_tag_write and not upload_pex:
        logging.warn(
            "--deps-cache-tag* specified without --upload-pex. Caching is disabled."
        )

    if update_code_location and not upload_pex:
        logging.warn(
            "--update-code-location specified without --upload-pex."
            " Code location may not work if pex files are not uploaded."
        )
    deps_cache_tags = DepsCacheTags(deps_cache_tag_read, deps_cache_tag_write)

    # always build
    with github_context.log_group("Building PEX Files"):
        location_builds = build_project(
            dagster_cloud_file,
            build_output_dir,
            upload_pex=upload_pex,
            deps_cache_tags=deps_cache_tags,
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

                # if a write cache_tag is specified, set or update the deps details
                if deps_cache_tags.deps_cache_tag_write:
                    # could be either a newly built pex or an published pex name copied from another tag
                    deps_pex_name = (
                        os.path.basename(location_build.deps_pex_path)
                        if location_build.deps_pex_path
                        else location_build.published_deps_pex
                    )

                    pex_registry.set_cached_deps_details(
                        location_build.deps_requirements.hash,
                        deps_cache_tags.deps_cache_tag_write,
                        deps_pex_name,
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
