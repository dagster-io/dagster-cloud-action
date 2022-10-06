import json
import logging
import os
import pprint
from typing import List, Optional
from urllib import request
from urllib.parse import parse_qs, urlsplit, urlunsplit
import requests

from dagster_cloud_cli import gql

from . import util

GENERATE_PUT_URL_QUERY = """
mutation GenerateServerlessPexUploadUrlMutation($filenames: [String!]!) {
    generateServerlessPexUploadUrl(filenames: $filenames, method:PUT, checkIfExists: true) {
        url
    }
}
"""

GENERATE_GET_URL_QUERY = """
mutation GenerateServerlessPexUploadUrlMutation($filenames: [String!]!) {
    generateServerlessPexUploadUrl(filenames: $filenames, method:GET, checkIfExists: true) {
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
            return [
                item["url"] for item in result["data"]["generateServerlessPexUploadUrl"]
            ]
        else:
            return None


def get_s3_urls_for_get(filenames: List[str]) -> Optional[List[str]]:
    with util.graphql_client("prod") as client:
        result = client.execute(
            GENERATE_GET_URL_QUERY,
            variable_values={"filenames": filenames},
        )

        if result["data"]:
            return [
                item["url"] for item in result["data"]["generateServerlessPexUploadUrl"]
            ]
        else:
            return None


def requirements_hash_filename(requirements_hash: str):
    return f"requirements-{requirements_hash}.txt"


def get_deps_pex_name_for_requirements_hash(requirements_hash: str) -> Optional[str]:
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


def upload_files(filepaths: List[str]):
    filenames = [os.path.basename(filepath) for filepath in filepaths]
    urls = get_s3_urls_for_put(filenames)
    if not urls:
        logging.error("Cannot upload files, did not get PUT urls for: %s", filenames)
        return

    # we expect response list to be in the same order as the request
    for filename, filepath, url in zip(filenames, filepaths, urls):
        logging.info("Uploading %r ...", filepath)
        logging.info("PUT Url: %r", url)
        # scheme, netloc, path, query, fragment = urlsplit(url)
        # base_url = urlunsplit((scheme, netloc, path, None, None))
        # fields = parse_qs(query)

        with open(filepath, "rb") as f:
            response = requests.put(url, data=f.read())
            if response.ok:
                logging.info("Upload successful: %s", filepath)
            else:
                logging.error("Upload failed for %r: %r", filepath, response)
                logging.error(response.content)


def get_file():
    print("getting url")
    urls = get_s3_urls_for_get([requirements_hash_filename("")])
    if not urls:
        print("fail")
        return

    for url in urls:
        scheme, netloc, path, query, fragment = urlsplit(url)
        base_url = urlunsplit((scheme, netloc, path, None, None))
        fields = parse_qs(query)

        pprint.pprint(url)
        pprint.pprint(fields)
        print(requests.get(url))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(get_file())
    # print(upload_files(["/tmp/build/source-f489c9f42778543b86574c46d9cfb5d178885702.pex"]))

# def upload_files(filepaths: List[str]):
