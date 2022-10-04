import base64
import logging
import os

from dagster_cloud_cli import gql


def get_registry_info():
    dagster_cloud_api_token = os.getenv("DAGSTER_CLOUD_API_TOKEN")
    if not dagster_cloud_api_token:
        raise ValueError("DAGSTER_CLOUD_API_TOKEN not defined")
    dagster_cloud_url = os.getenv("DAGSTER_CLOUD_URL")
    if not dagster_cloud_url:
        raise ValueError("DAGSTER_CLOUD_URL not defined")

    url = dagster_cloud_url + "/prod"

    with gql.graphql_client_from_url(url, dagster_cloud_api_token) as client:
        ecr_info = gql.get_ecr_info(client)
        registry_url = ecr_info["registry_url"]
        aws_region = ecr_info.get("aws_region", "us-west-2")
        aws_token = ecr_info["aws_auth_token"]
        custom_base_image_allowed = ecr_info["allow_custom_base"]

        if not aws_token or not registry_url:
            logging.error("No aws_token or registry_url found.")
            return

        username, password = base64.b64decode(aws_token).decode("utf-8").split(":")

        logging.info("Loaded registry info. registry_url: %r", ecr_info["registry_url"])
