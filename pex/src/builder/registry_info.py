import base64
import logging

from dagster_cloud_cli import gql

from . import util


def get_registry_info():
    with util.graphql_client("prod") as client:
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
