import json


def test_deploy_full_deployment_github(exec_context, action_docker_image_id):
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
        }
    )

    exec_context.stub_command(
        "dagster-cloud",
        {
            "workspace add-location --url http://dagster.cloud/test/prod "
            "--api-token api-token --location-file some-location/dagster_cloud.yaml "
            "--location-name some-location --image some-location-registry:prod-some-location-sha "
            "--location-load-timeout 600 --agent-heartbeat-timeout 90 "
            "--git-url https://github.com//some-org/some-project/tree/sha12345 "
            "--commit-hash sha12345": "",
        },
    )
    exec_context.run_docker_command(action_docker_image_id, "/deploy.sh")
    assert "Deploying location some-location" in exec_context.get_stdout()


def test_deploy_full_deployment_gitlab(exec_context, action_docker_image_id):
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
        }
    )

    exec_context.stub_command(
        "dagster-cloud",
        {
            "workspace add-location --url http://dagster.cloud/test/prod "
            "--api-token api-token --location-file some-location/dagster_cloud.yaml "
            "--location-name some-location --image some-location-registry:prod-some-location-sha "
            "--location-load-timeout 600 --agent-heartbeat-timeout 90 "
            "--git-url https://gitlab.com/some-org/some-project//-/commit/sha12345 "
            "--commit-hash sha12345": "",
        },
    )
    exec_context.run_docker_command(action_docker_image_id, "/deploy.sh")
    assert "Deploying location some-location" in exec_context.get_stdout()
