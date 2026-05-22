import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

"""
Creates or updates a build status comment on a Pull Request, for branch deployments.
"""

GITHUB_API = "https://api.github.com"

SUCCESS_IMAGE_URL = (
    "https://raw.githubusercontent.com/dagster-io/dagster-cloud-action/main/assets/success.png"
)
PENDING_IMAGE_URL = (
    "https://raw.githubusercontent.com/dagster-io/dagster-cloud-action/main/assets/pending.png"
)
FAILED_IMAGE_URL = (
    "https://raw.githubusercontent.com/dagster-io/dagster-cloud-action/main/assets/failed.png"
)


def main():
    token = os.getenv("GITHUB_TOKEN")
    pr_id = int(os.getenv("INPUT_PR"))
    repo_id = os.getenv("GITHUB_REPOSITORY")
    action = os.getenv("INPUT_ACTION")
    deployment_name = os.getenv("INPUT_DEPLOYMENT")

    org_url = os.getenv("DAGSTER_CLOUD_URL")
    github_run_url = os.getenv("GITHUB_RUN_URL")

    location_name = os.getenv("INPUT_LOCATION_NAME")

    comment_to_update_id = _find_existing_comment(token, repo_id, pr_id, location_name)

    deployment_url = f"{org_url}/{deployment_name}/home"

    message = f"[View in Cloud]({deployment_url})"
    image_url = SUCCESS_IMAGE_URL

    if action == "pending":
        message = f"[Building...]({github_run_url})"
        image_url = PENDING_IMAGE_URL
    elif action == "failed":
        message = f"[Deploy failed]({github_run_url})"
        image_url = FAILED_IMAGE_URL

    status_image = f'[<img src="{image_url}" width=25 height=25/>]({github_run_url})'

    time_str = datetime.datetime.now(datetime.timezone.utc).strftime("%b %d, %Y at %I:%M %p (%Z)")

    body = f"""
Your pull request is automatically being deployed to Dagster Cloud.

| Location          | Status          | Link    | Updated         |
| ----------------- | --------------- | ------- | --------------- |
| `{location_name}` | {status_image}  | {message}  | {time_str}      |
    """

    if comment_to_update_id is not None:
        _request(
            "PATCH",
            f"{GITHUB_API}/repos/{repo_id}/issues/comments/{comment_to_update_id}",
            token,
            {"body": body},
        )
    else:
        _request(
            "POST",
            f"{GITHUB_API}/repos/{repo_id}/issues/{pr_id}/comments",
            token,
            {"body": body},
        )


def _find_existing_comment(token, repo_id, pr_id, location_name):
    # Check if a comment exists on the PR from the github actions user
    # which is specific to this location name
    page = 1
    while True:
        url = (
            f"{GITHUB_API}/repos/{repo_id}/issues/{pr_id}/comments"
            f"?per_page=100&page={page}"
        )
        comments = _request("GET", url, token)
        if not comments:
            return None
        for comment in comments:
            user_login = (comment.get("user") or {}).get("login")
            body = comment.get("body") or ""
            if (
                user_login == "github-actions[bot]"
                and "Dagster Cloud" in body
                and f"`{location_name}`" in body
            ):
                return comment["id"]
        if len(comments) < 100:
            return None
        page += 1


def _request(method, url, token, payload=None):
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "dagster-cloud-action",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            if not body:
                return None
            return json.loads(body)
    except urllib.error.HTTPError as err:
        print(f"GitHub API {method} {url} failed: {err}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
