import json

import pytest


def test_deploy_full_deployment_github(tmp_path, exec_context, action_docker_image_id):
    output_file = tmp_path / "output.txt"
    output_file.touch()

    exec_context.set_env(
        {
            "GITHUB_ACTIONS": "true",
            "DAGSTER_CLOUD_URL": "http://dagster.cloud/test",
            "INPUT_DEPLOYMENT": "prod",
            "DAGSTER_CLOUD_API_TOKEN": "api-token",
            "INPUT_LOCATION": json.dumps(
                {
                    "name": "some-location",
                    "build_folder": "some-location-build-folder",
                    "registry": "some-location-registry",
                    "location_file": "some-location/dagster_cloud.yaml",
                }
            ),
            "GITHUB_SERVER_URL": "https://github.com/",
            "GITHUB_REPOSITORY": "some-org/some-project",
            "GITHUB_SHA": "sha12345",
            "INPUT_IMAGE_TAG": "prod-some-location-sha",
            "GITHUB_OUTPUT": output_file.name,
        }
    )

    exec_context.stub_command(
        "dagster-cloud",
        {
            "workspace add-location --url http://dagster.cloud/test/prod "
            "--api-token api-token --location-file some-location/dagster_cloud.yaml "
            "--location-name some-location --image some-location-registry:prod-some-location-sha "
            "--location-load-timeout 3600 --agent-heartbeat-timeout 90 "
            "--git-url https://github.com//some-org/some-project/tree/sha12345 "
            "--commit-hash sha12345": "",
        },
    )
    exec_context.run_docker_command(action_docker_image_id, "/deploy.sh")
    assert "Deploying location some-location" in exec_context.get_stdout()
    assert "deployment=prod" in output_file.read_text()


def test_deploy_full_deployment_gitlab(exec_context, action_docker_image_id, tmp_path):
    output_file = tmp_path / "output.txt"
    output_file.touch()

    exec_context.set_env(
        {
            "GITLAB_CI": "true",
            "DAGSTER_CLOUD_URL": "http://dagster.cloud/test",
            "INPUT_DEPLOYMENT": "prod",
            "DAGSTER_CLOUD_API_TOKEN": "api-token",
            "INPUT_LOCATION": json.dumps(
                {
                    "name": "some-location",
                    "build_folder": "some-location-build-folder",
                    "registry": "some-location-registry",
                    "location_file": "some-location/dagster_cloud.yaml",
                }
            ),
            "CI_PROJECT_URL": "https://gitlab.com/some-org/some-project/",
            "CI_COMMIT_SHORT_SHA": "sha12345",
            "INPUT_IMAGE_TAG": "prod-some-location-sha",
            "GITHUB_OUTPUT": output_file.name,
        }
    )

    exec_context.stub_command(
        "dagster-cloud",
        {
            "workspace add-location --url http://dagster.cloud/test/prod "
            "--api-token api-token --location-file some-location/dagster_cloud.yaml "
            "--location-name some-location --image some-location-registry:prod-some-location-sha "
            "--location-load-timeout 3600 --agent-heartbeat-timeout 90 "
            "--git-url https://gitlab.com/some-org/some-project//-/commit/sha12345 "
            "--commit-hash sha12345": "",
        },
    )
    exec_context.run_docker_command(action_docker_image_id, "/deploy.sh")
    assert "Deploying location some-location" in exec_context.get_stdout()
    assert "deployment=prod" in output_file.read_text()


def test_deploy_full_deployment_unsupported_ci(exec_context, action_docker_image_id):
    with pytest.raises(Exception, match="Running in an unsupported CI environment"):
        exec_context.run_docker_command(action_docker_image_id, "/deploy.sh")
