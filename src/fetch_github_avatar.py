import os
import sys

import requests

from github_session import GITHUB_API, github_session

"""
Fetches a user's avatar from the Github API based on email or username
"""


def main():
    token = os.getenv("GITHUB_TOKEN")
    repo_id = os.getenv("GITHUB_REPOSITORY")
    commit_sha = os.getenv("GITHUB_SHA")

    session = github_session(token)
    try:
        resp = session.get(f"{GITHUB_API}/repos/{repo_id}/commits/{commit_sha}", timeout=60)
        resp.raise_for_status()
    except requests.RequestException as err:
        print(f"Failed to fetch commit {commit_sha}: {err}", file=sys.stderr)
        sys.exit(1)

    author = resp.json().get("author") or {}
    print(author.get("avatar_url", ""))


if __name__ == "__main__":
    main()
