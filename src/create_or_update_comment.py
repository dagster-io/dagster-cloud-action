import datetime
import github
from github import Github
import os

"""
Creates or updates a build status comment on a Pull Request, for branch deployments.
"""

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
    # Fetch various pieces of info from the environment
    g = Github(os.getenv("GITHUB_TOKEN"))
    pr_id = int(os.getenv("INPUT_PR"))
    repo_id = os.getenv("GITHUB_REPOSITORY")
    action = os.getenv("INPUT_ACTION")
    deployment_name = os.getenv("INPUT_DEPLOYMENT")

    org_url = os.getenv("DAGSTER_CLOUD_URL")
    github_run_url = os.getenv("GITHUB_RUN_URL")

    location_name = os.getenv("INPUT_LOCATION_NAME")

    repo = g.get_repo(repo_id)
    pr = repo.get_pull(pr_id)

    comments = pr.get_issue_comments()
    comment_to_update = None

    # Check if a comment exists on the PR from the github actions user
    # which is specific to this location name
    # otherwise we create a new comment
    for comment in comments:
        if (
            comment.user.login == "github-actions[bot]"
            and "Dagster Cloud" in comment.body
            and f"`{location_name}`" in comment.body
        ):
            comment_to_update = comment
            break

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

    message = f"""
Your pull request is automatically being deployed to Dagster Cloud.

| Location          | Status          | Link    | Updated         |
| ----------------- | --------------- | ------- | --------------- | 
| `{location_name}` | {status_image}  | {message}  | {time_str}      |
    """

    if comment_to_update:
        comment_to_update.edit(message)
    else:
        pr.create_issue_comment(message)


if __name__ == "__main__":
    main()
