from audioop import add
import base64
import logging
import pprint
import sys

from dagster_cloud_cli import gql, config_utils

from . import util

# NOTE: this works but requires the unmerged branch of dagster_cloud_cli instead of the
# published version.
def add_or_update_code_location(deployment_name, location_name, **location_kwargs):
    with util.graphql_client("prod") as client:
        location_document = config_utils.get_location_document(
            location_name, location_kwargs
        )
        gql.add_or_update_code_location(client, location_document)
        name = location_document["location_name"]
        logging.info(f"Added or updated location {name}.")


def wait_for_load():
    with util.graphql_client("prod") as client:
        # TODO
        pass


def create_or_update_branch_deployment(
    repo_name, branch_name, commit_hash, timestamp, **kwargs
):
    # kwargs typically includes:
    # branch_url=branch_url,
    # pull_request_url=pull_request_url,
    # pull_request_status=pull_request_status,
    # pull_request_number=pull_request_number,
    # commit_message=commit_message,
    # author_name=author_name,
    # author_email=author_email,
    # author_avatar_url=author_avatar_url,

    with util.graphql_client("prod") as client:
        gql.create_or_update_branch_deployment(
            client,
            repo_name=repo_name,
            branch_name=branch_name,
            commit_hash=commit_hash,
            timestamp=timestamp,
            **kwargs,
        )


if __name__ == "__main__":
    # # simple test entry point for add_or_update_code_location
    # deployment_name, location_name, args = sys.argv[1:4]
    # kwargs = dict(arg.split('=', 1) for arg in args.split(','))
    # add_or_update_code_location(deployment_name, location_name, **kwargs)

    # simple test entry point for create_or_update_branch_deployment
    from . import github_context

    event = github_context.github_event()
    print("Read github event:")
    pprint.pprint(event.__dict__)
    if not event.branch_name:
        print("Not in a branch, not creating branch deployment")
    else:
        create_or_update_branch_deployment(
            event.repo_name,
            event.branch_name,
            event.github_sha,
            event.timestamp,
            branch_url=event.branch_url,
            pull_request_url=event.pull_request_url,
            pull_request_status=event.pull_request_status,
            pull_request_number=event.pull_request_id,
        )
