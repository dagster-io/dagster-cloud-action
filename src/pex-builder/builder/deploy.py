# end-to-end workflow for rebuilding and publishing code locations

import dataclasses
import logging
import os
import threading
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

    code_location_update_error: Optional[Exception] = None


@dataclass
class DepsCacheTags:
    deps_cache_from_tag: Optional[str]
    deps_cache_to_tag: Optional[str]


def build_project(
    dagster_cloud_yaml_file: str,
    output_directory: str,
    upload_pex: bool,
    deps_cache_tags: DepsCacheTags,
    python_version: version.Version,
    should_notify: bool = False,
) -> List[LocationBuild]:
    """Rebuild pexes for code locations in a project."""

    locations = parse_workspace.get_locations(dagster_cloud_yaml_file)

    if should_notify:
        for location in locations:
            notify(None, location.name, "pending")

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

        # if a --deps-cache-from is specified, don't build deps.pex files if it is already published
        if upload_pex and deps_cache_tags.deps_cache_from_tag:
            published_deps_pex_info = pex_registry.get_cached_deps_details(
                deps_requirements.hash, deps_cache_tags.deps_cache_from_tag
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
                deps_cache_tags.deps_cache_from_tag,
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
                deps_cache_tags.deps_cache_from_tag,
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
    # TODO: switch to private released versions
    return (
        f"public.ecr.aws/dagster/dagster-cloud-serverless-base-{py_tag}:1.0.15-pex-execute-run"
    )


def notify(deployment_name: Optional[str], location_name: str, action: str):
    if github_event:
        github_context.update_pr_comment(
            github_event,
            action=action,
            deployment_name=deployment_name,
            location_name=location_name,
        )


github_event: Optional[github_context.GithubEvent] = None


def load_github_event(project_dir):
    global github_event
    github_event = github_context.get_github_event(project_dir)


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
    "--deps-cache-from",
    type=str,
    required=False,
    help="Try to reuse a pre-existing deps pex file. A deps pex file is reused if it was "
    "built with a --deps-cache-to value that matches this flag value, AND the requirements.txt "
    "and setup.py were identical.",
)
@click.option(
    "--deps-cache-to",
    type=str,
    required=False,
    help="Allow reusing the generated deps pex and associate with the given tag. "
    "See --deps-cache-from for how to reuse deps pex files.",
)
@click.option(
    "--update-code-location",
    is_flag=True,
    show_default=True,
    default=False,
    help="Update code location to use new PEX files.",
)
@click.option(
    "--code-location-details",
    callback=util.parse_kv,
    help="Syntax: --code-location-details deployment=NAME,commit_hash=HASH. "
    "When not provided, details are inferred from the github action environment.",
)
@util.python_version_option()
def cli(
    dagster_cloud_file,
    build_output_dir,
    upload_pex,
    deps_cache_to,
    deps_cache_from,
    update_code_location,
    code_location_details,
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
    reused using the --deps-cache-* flags.

    To build the deps-HASH.pex once and reuse, specify the same value in both --deps-cache-* flags:
    $ builder.pex deploy ... --deps-cache-from=main --deps-cache-to=main ...

    To force a rebuild for a specific cache tag, specify only the --deps-cache-to flag but not the
    --deps-cache-from flag:
    $ builder.pex deploy ... --deps-cache-to=main ...

    To seed a new cache from an existing cache, specify the source tag in the --deps-cache-from flag:
    $ builder.pex deploy ... --deps-cache-from=main --deps-cache-to=branch1 ...

    In addition to the --deps-cache-from flag, the content of setup.py and requirements.txt must also
    match for a deps pex to be reused.
    """
    deploy_main(
        dagster_cloud_file,
        build_output_dir,
        upload_pex=upload_pex,
        deps_cache_from_tag=deps_cache_from,
        deps_cache_to_tag=deps_cache_to,
        update_code_location=update_code_location,
        code_location_details=code_location_details,
        python_version=python_version,
    )


def deploy_main(
    dagster_cloud_file: str,
    build_output_dir: str,
    *,
    upload_pex: bool,
    deps_cache_from_tag: Optional[str],
    deps_cache_to_tag: Optional[str],
    update_code_location: bool,
    code_location_details: Optional[Dict[str, str]],
    python_version: str,
):
    # We don't have strict checking, but print warnings in case flags don't make sense
    if (deps_cache_from_tag or deps_cache_to_tag) and not upload_pex:
        logging.warning(
            "--deps-cache-tag* specified without --upload-pex. Caching is disabled."
        )

    if update_code_location and not upload_pex:
        logging.warning(
            "--update-code-location specified without --upload-pex."
            " Code location may not work if pex files are not uploaded."
        )
    if update_code_location:
        if code_location_details:
            if (
                "deployment" not in code_location_details
                or "commit_hash" not in code_location_details
            ):
                raise ValueError(
                    "--code-location-details value must include name and commit_hash, eg "
                    "'deployment=prod,commit_hash=1234a'",
                    code_location_details,
                )
        else:
            load_github_event(os.path.dirname(dagster_cloud_file))

    deps_cache_tags = DepsCacheTags(deps_cache_from_tag, deps_cache_to_tag)

    # always build
    with github_context.log_group("Building PEX Files"):
        location_builds = build_project(
            dagster_cloud_file,
            build_output_dir,
            upload_pex=upload_pex,
            deps_cache_tags=deps_cache_tags,
            python_version=util.parse_python_version(python_version),
            should_notify=update_code_location,
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

                # if a --deps-cache-to cache_tag is specified, set or update the deps details
                if deps_cache_tags.deps_cache_to_tag:
                    # could be either a newly built pex or an published pex name copied from another tag
                    deps_pex_name = (
                        os.path.basename(location_build.deps_pex_path)
                        if location_build.deps_pex_path
                        else location_build.published_deps_pex
                    )

                    pex_registry.set_cached_deps_details(
                        location_build.deps_requirements.hash,
                        deps_cache_tags.deps_cache_to_tag,
                        deps_pex_name,
                        dagster_version=location_build.dagster_version,
                    )
    else:
        logging.info("Skipping upload to pex registry: no --upload-pex")

    # update code location if enabled
    if update_code_location:
        if code_location_details:
            deployment = code_location_details["deployment"]
            commit_hash = code_location_details["commit_hash"]
        elif github_event:
            logging.info(
                "No --code-location-details, inferring from github environment."
            )
            deployment = "prod"  # default

            commit_hash = github_event.github_sha
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
                        raise ValueError(
                            "Could not create branch deployment", github_event
                        )
        else:
            raise ValueError(
                "No --code-location-details provided and not running in Github, "
                "cannot update code location."
            )

        with github_context.log_group(f"Updating code locations"):
            # do updates in independent threads so we can isolate errors
            threads = [
                threading.Thread(
                    target=run_code_location_update,
                    name=location_build.location.name,
                    args=(deployment, commit_hash, dagster_cloud_file, location_build),
                )
                for location_build in location_builds
            ]
            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

            # once all locations updates are done, fail if any failed
            for location_build in location_builds:
                if location_build.code_location_update_error:
                    raise location_build.code_location_update_error

    else:
        logging.info("Skipping code location update: no --update-code-location")

    logging.info("All done")

    return location_builds


def run_code_location_update(
    deployment: str,
    commit_hash: str,
    dagster_cloud_file: str,
    location_build: LocationBuild,
):
    location_name = location_build.location.name
    try:
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
            commit_hash=commit_hash,
        )

        code_location.wait_for_load(
            deployment_name=deployment,
            location_names=[location_build.location.name],
        )
        notify(
            deployment_name=deployment, location_name=location_name, action="success"
        )
    except Exception as err:
        location_build.code_location_update_error = err

        logging.exception("Error updating code location %r", location_name)
        notify(deployment_name=deployment, location_name=location_name, action="failed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cli()
