import datetime
import os
import sys

from github_session import GITHUB_API, github_session

"""
Creates or updates a build status comment on a Pull Request, for branch deployments.
"""

COMMENTS_PAGE_SIZE = 100

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

    # PATCH on a specific comment is effectively idempotent here (same body,
    # same id), so opt it in to retries. POST is left out to avoid duplicate
    # comment creation if GitHub processes the request but the response is lost.
    session = github_session(token, retry_methods=("GET", "PATCH"))
    comment_to_update_id = _find_existing_comment(session, repo_id, pr_id, location_name)

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
        resp = session.patch(
            f"{GITHUB_API}/repos/{repo_id}/issues/comments/{comment_to_update_id}",
            json={"body": body},
            timeout=60,
        )
    else:
        resp = session.post(
            f"{GITHUB_API}/repos/{repo_id}/issues/{pr_id}/comments",
            json={"body": body},
            timeout=60,
        )
    resp.raise_for_status()


def _find_existing_comment(session, repo_id, pr_id, location_name):
    # Check if a comment exists on the PR from the github actions user
    # which is specific to this location name
    page = 1
    while True:
        resp = session.get(
            f"{GITHUB_API}/repos/{repo_id}/issues/{pr_id}/comments",
            params={"per_page": COMMENTS_PAGE_SIZE, "page": page},
            timeout=60,
        )
        resp.raise_for_status()
        comments = resp.json()
        if not comments:
            return None
        for comment in comments:
            user_login = (comment.get("user") or {}).get("login")
            comment_body = comment.get("body") or ""
            if (
                user_login == "github-actions[bot]"
                and "Dagster Cloud" in comment_body
                and f"`{location_name}`" in comment_body
            ):
                return comment["id"]
        if len(comments) < COMMENTS_PAGE_SIZE:
            return None
        page += 1


if __name__ == "__main__":
    sys.exit(main())
