import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

GITHUB_API = "https://api.github.com"


def github_session(token, retry_methods=("GET",)):
    """A requests.Session preconfigured for the GitHub REST API.

    Sets the recommended Accept / API-version / User-Agent headers and a
    bearer Authorization header when a token is provided, and mounts an
    HTTPAdapter that retries transient 429/5xx responses for the given
    HTTP methods (idempotent methods only by default).
    """
    retry = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(retry_methods),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "dagster-cloud-action",
        }
    )
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    return session
