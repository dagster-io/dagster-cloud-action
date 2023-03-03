#!/usr/bin/env python

import datetime
import gitlab
import os
import sys

"""
Creates or updates a build status comment on a Pull Request, for branch deployments.
"""

SUCCESS_IMAGE_URL = "https://raw.githubusercontent.com/dagster-io/dagster-cloud-action/main/assets/success.png"
PENDING_IMAGE_URL = "https://raw.githubusercontent.com/dagster-io/dagster-cloud-action/main/assets/pending.png"
FAILED_IMAGE_URL = "https://raw.githubusercontent.com/dagster-io/dagster-cloud-action/main/assets/failed.png"


def notify(deployment, action, location_name):
    # Fetch various pieces of info from the environment
    client = gitlab.Gitlab(job_token=os.getenv("CI_JOB_TOKEN"))
    run_url = os.getenv("CI_JOB_URL")
    org_url = os.getenv("DAGSTER_CLOUD_URL")
    project = client.projects.get(os.getenv("CI_PROJECT_PATH"))
    mr = project.mergerequests.get(os.getenv("CI_MERGE_REQUEST_IID"))

    discussions = mr.discussions.list()
    discussion_to_update = None
    note_to_update = None
    for discussion in discussions:
        notes = discussion.attributes["notes"]
        for note in notes:
            if (
                # comment.user.login == "github-actions[bot]"
                # and "Dagster Cloud" in comment.body
                "Dagster Cloud" in note["body"]
                and f"`{location_name}`" in note["body"]
            ):
                note_to_update = note["id"]
                discussion_to_update = discussion
                break

    # Check if a comment exists on the PR from the github actions user
    # which is specific to this location name
    # otherwise we create a new comment

    deployment_url = f"{org_url}/{deployment}/home"

    message = f"[View in Cloud]({deployment_url})"
    image_url = SUCCESS_IMAGE_URL

    if action == "pending":
        message = f"[Building...]({run_url})"
        image_url = PENDING_IMAGE_URL
    elif action == "failed":
        message = f"[Deploy failed]({run_url})"
        image_url = FAILED_IMAGE_URL

    status_image = f'[<img src="{image_url}" width=25 height=25/>]({run_url})'

    time_str = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%b %d, %Y at %I:%M %p (%Z)"
    )

    message = f"""
Your pull request is automatically being deployed to Dagster Cloud.

| Location          | Status          | Link    | Updated         |
| ----------------- | --------------- | ------- | --------------- |
| `{location_name}` | {status_image}  | {message}  | {time_str}      |
    """

    if discussion_to_update:
        note = discussion.notes.get(note_to_update)
        note.body = message
        note.save()
    else:
        mr.discussions.create({"body": message})


if __name__ == "__main__":
    deployment = sys.argv[1]
    action = sys.argv[2]
    location_name = sys.argv[3]
    notify(deployment, action, location_name)
