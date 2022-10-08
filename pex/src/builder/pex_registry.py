import json
import logging
import os
import sys
from tempfile import TemporaryDirectory
from typing import List, Optional
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


def get_deps_pex_name_from_requirements_hash(
    requirements_hash: str,
) -> Optional[str]:
    """Returns the 'deps-<HASH>.pex' filename for requirements_hash if already uploaded."""
    urls = get_s3_urls_for_get([requirements_hash_filename(requirements_hash)])
    if not urls:
        return None

    url = urls[0]

    result = requests.get(url)
    if result.ok:
        data = json.loads(result.content)
        return data["deps_pex_name"]
    return None


def set_requirements_hash_values(requirements_hash: str, deps_pex_name: str):
    """Saves the deps_pex_name into the requirements hash file."""
    filename = requirements_hash_filename(requirements_hash)
    content = json.dumps({"deps_pex_name": deps_pex_name})
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
