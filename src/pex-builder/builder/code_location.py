import logging
from typing import List, Optional

from dagster_cloud_cli import config_utils, gql
from dagster_cloud_cli.commands import workspace

from . import github_context, util

# This module can directly call dagster_cloud_cli once the pex changes are released with the cli.
# Right now there is some code duplication between here and the cli commands.


def add_or_update_code_location(deployment_name, location_name, **location_kwargs):
    with util.graphql_client(deployment_name) as client:
        # config_utils can't validate a location with pex_tag (yet). once dagster-cloud-cli is
        # published with the pex_tag changes, we don't need to hack inject the 'pex_tag'.
        pex_tag = location_kwargs.pop("pex_tag") if "pex_tag" in location_kwargs else None
        location_document = config_utils.get_location_document(location_name, location_kwargs)
        if pex_tag:
            location_document["pex_metadata"] = {"pex_tag": pex_tag}  # hack inject

        gql.add_or_update_code_location(client, location_document)
        logging.info(
            "Added or updated location %r for deployment %r with %r",
            location_name,
            deployment_name,
            location_document,
        )


def wait_for_load(
    deployment_name: str,
    location_names: List[str],
    location_load_timeout=600,
    agent_heartbeat_timeout=90,
):
    with util.graphql_client(deployment_name) as client:
        workspace.wait_for_load(
            client,
            locations=location_names,
            location_load_timeout=location_load_timeout,
            agent_heartbeat_timeout=agent_heartbeat_timeout,
            # url=util.url_for_deployment(deployment_name=deployment_name),
        )


def create_or_update_branch_deployment(
    repo_name, branch_name, commit_hash, timestamp, **kwargs
) -> str:
    # typical kwargs:
    # branch_url=branch_url,
    # pull_request_url=pull_request_url,
    # pull_request_status=pull_request_status,
    # pull_request_number=pull_request_number,
    # commit_message=commit_message,
    # author_name=author_name,
    # author_email=author_email,
    # author_avatar_url=author_avatar_url,

    # TODO: determine the parent full deployment name based on context.
    # For serverless there is only one full deployment so this works for now.
    with util.graphql_client("prod") as client:
        return gql.create_or_update_branch_deployment(
            client,
            repo_name=repo_name,
            branch_name=branch_name,
            commit_hash=commit_hash,
            timestamp=timestamp,
            **kwargs,
        )


def create_or_update_branch_deployment_from_github_context(
    github_event: github_context.GithubEvent,
) -> Optional[str]:
    event = github_event
    logging.debug("Read github event GithubEvent(%r)", event.__dict__)
    if not event.branch_name:
        logging.info("Not in a branch, not creating branch deployment")
        return None
    else:
        deployment_name = create_or_update_branch_deployment(
            event.repo_name,
            event.branch_name,
            event.github_sha,
            event.timestamp,
            branch_url=event.branch_url,
            pull_request_url=event.pull_request_url,
            pull_request_status=event.pull_request_status,
            pull_request_number=event.pull_request_id,
            author_name=event.author_name,
            author_email=event.author_email,
            commit_message=event.commit_msg,
            author_avatar_url=github_event.get_github_avatar_url(),
        )
        logging.info(
            "Got branch deployment %r for branch %r",
            deployment_name,
            event.branch_name,
        )
        return deployment_name
