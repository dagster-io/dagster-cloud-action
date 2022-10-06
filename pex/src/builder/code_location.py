import logging
import pprint
from typing import Optional

from . import github_context

import sys

from dagster_cloud_cli import gql, config_utils

from . import util


def add_or_update_code_location(deployment_name, location_name, **location_kwargs):
    with util.graphql_client(deployment_name) as client:
        # config_utils can't validate a location with pex_tag (yet). once dagster-cloud-cli is
        # published with the pex_tag changes, we don't need to hack inject the 'pex_tag'.
        pex_tag = (
            location_kwargs.pop("pex_tag") if "pex_tag" in location_kwargs else None
        )
        location_document = config_utils.get_location_document(
            location_name, location_kwargs
        )
        if pex_tag:
            location_document["pex_tag"] = pex_tag  # hack inject

        gql.add_or_update_code_location(client, location_document)
        name = location_document["location_name"]
        logging.info(
            f"Added or updated location %r for deployment %r with %r",
            location_name,
            deployment_name,
            location_kwargs,
        )


def wait_for_load():
    with util.graphql_client("prod") as client:
        # TODO
        pass


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

    with util.graphql_client("prod") as client:
        return gql.create_or_update_branch_deployment(
            client,
            repo_name=repo_name,
            branch_name=branch_name,
            commit_hash=commit_hash,
            timestamp=timestamp,
            **kwargs,
        )


def create_or_update_branch_deployment_from_github_context() -> Optional[str]:
    event = github_context.github_event()
    logging.info("Read github event GithubEvent(%r)", event.__dict__)
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
            pull_request_status=event.pull_request_status.upper(),
            pull_request_number=event.pull_request_id,
        )
        logging.info(
            "Created branch deployment %r for branch %r",
            deployment_name,
            event.branch_name,
        )
        return deployment_name


if __name__ == "__main__":
    # # simple test entry points

    if sys.argv[1] == "add_or_update_code_location":
        deployment_name, location_name, args = sys.argv[2:5]
        kwargs = dict(arg.split("=", 1) for arg in args.split(","))
        add_or_update_code_location(deployment_name, location_name, **kwargs)
    elif sys.argv[1] == "create_or_update_branch_deployment":
        create_or_update_branch_deployment_from_github_context()

    # simple test entry point for create_or_update_branch_deployment
