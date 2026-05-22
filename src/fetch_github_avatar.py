import json
import os
import sys
import urllib.error
import urllib.request

"""
Fetches a user's avatar from the Github API based on email or username
"""

GITHUB_API = "https://api.github.com"


def main():
    token = os.getenv("GITHUB_TOKEN")
    repo_id = os.getenv("GITHUB_REPOSITORY")
    commit_sha = os.getenv("GITHUB_SHA")

    url = f"{GITHUB_API}/repos/{repo_id}/commits/{commit_sha}"
    req = urllib.request.Request(url, headers=_headers(token))
    try:
        with urllib.request.urlopen(req) as resp:
            commit = json.load(resp)
    except urllib.error.HTTPError as err:
        print(f"Failed to fetch commit {commit_sha}: {err}", file=sys.stderr)
        sys.exit(1)

    author = commit.get("author") or {}
    print(author.get("avatar_url", ""))


def _headers(token):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "dagster-cloud-action",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


if __name__ == "__main__":
    main()
