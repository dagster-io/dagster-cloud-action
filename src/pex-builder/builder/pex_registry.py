import json
import logging
import os
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Optional

import requests

from . import util

GENERATE_PUT_URL_QUERY = """
mutation GenerateServerlessPexUrlMutation($filenames: [String!]!) {
    generateServerlessPexUrl(filenames: $filenames, method:PUT) {
        url
    }
}
"""

GENERATE_GET_URL_QUERY = """
mutation GenerateServerlessPexUrlMutation($filenames: [String!]!) {
    generateServerlessPexUrl(filenames: $filenames, method:GET) {
        url
    }
}
"""


def get_s3_urls_for_put(filenames: List[str]) -> Optional[List[str]]:
    with util.graphql_client("prod") as client:
        result = client.execute(
            GENERATE_PUT_URL_QUERY,
            variable_values={"filenames": filenames},
        )

        if result["data"]:
            return [item["url"] for item in result["data"]["generateServerlessPexUrl"]]
        else:
            return None


def get_s3_urls_for_get(filenames: List[str]) -> Optional[List[str]]:
    with util.graphql_client("prod") as client:
        result = client.execute(
            GENERATE_GET_URL_QUERY,
            variable_values={"filenames": filenames},
        )

        if result["data"]:
            return [item["url"] for item in result["data"]["generateServerlessPexUrl"]]
        else:
            return None


def requirements_hash_filename(requirements_hash: str):
    return f"requirements-{requirements_hash}.txt"


def get_requirements_hash_values(
    requirements_hash: str,
) -> Optional[Dict[str, Any]]:
    """Returns a metadata dict for the requirements_hash. The dict contains:
    'deps_pex_name': filename for the deps pex, eg 'deps-123234334.pex'
    'dagster_version': dagster package version included in the deps, eg '1.0.14'
    """
    urls = get_s3_urls_for_get([requirements_hash_filename(requirements_hash)])
    if not urls:
        return None

    url = urls[0]
    if not url:
        return None

    result = requests.get(url)
    if result.ok:
        data = json.loads(result.content)
        # Don't return partial information
        if "deps_pex_name" in data and "dagster_version" in data:
            return data
    return None


def set_requirements_hash_values(
    requirements_hash: str, deps_pex_name: str, dagster_version: str
):
    """Saves the deps_pex_name and dagster_version into the requirements hash file."""
    filename = requirements_hash_filename(requirements_hash)
    content = json.dumps(
        {"deps_pex_name": deps_pex_name, "dagster_version": dagster_version}
    )
    with TemporaryDirectory() as tmp_dir:
        filepath = os.path.join(tmp_dir, filename)
        with open(filepath, "w") as f:
            f.write(content)

        upload_files([filepath])


def upload_files(filepaths: List[str]):
    filenames = [os.path.basename(filepath) for filepath in filepaths]
    urls = get_s3_urls_for_put(filenames)
    if not urls:
        logging.error("Cannot upload files, did not get PUT urls for: %s", filenames)
        return

    # we expect response list to be in the same order as the request
    for filename, filepath, url in zip(filenames, filepaths, urls):
        if not url:
            logging.info("No upload URL received for %r - skipping", filepath)
            continue

        logging.info("Uploading %r ...", filepath)
        with open(filepath, "rb") as f:
            response = requests.put(url, data=f)
            if response.ok:
                logging.info("Upload successful: %s", filepath)
            else:
                logging.error("Upload failed for %r: %r", filepath, response)
                logging.error("Upload URL: %r", url)
                logging.error(response.content)
