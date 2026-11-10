import pytest
import yaml


@pytest.fixture
def gitlab_project(exec_context):
    exec_context.tmp_file_path("dagster_cloud.yaml").write_text(
        yaml.dump({"locations": [{"location_name": "foo", "code_source": {"python_file": "repo.py"}}]})
    )
    exec_context.set_env(
        {
            "DAGSTER_CLOUD_URL": "https://some-org.dagster.cloud",
            "CI_PROJECT_NAME": "some-project",
            "CI_PROJECT_URL": "https://gitlab.com/some-org/some-project",
            "CI_COMMIT_SHORT_SHA": "sha12345",
            "CI_COMMIT_BRANCH": "main",
        }
    )
    return exec_context


@pytest.mark.parametrize(
    "env, expected_python_version",
    [
        ({}, "3.14"),
        ({"PYTHON_VERSION": "3.12"}, "3.12"),
    ],
)
def test_gitlab_deploy_python_version(
    gitlab_project, action_docker_image_id, env, expected_python_version
):
    gitlab_project.set_env(env)
    gitlab_project.stub_command(
        "dagster-cloud",
        {
            "serverless deploy-python-executable --location-name=foo "
            "--location-file=/mount/dagster_cloud.yaml --commit-hash=sha12345 "
            "--git-url=https://gitlab.com/some-org/some-project/commit/sha12345 "
            f"--python-version={expected_python_version} "
            "--deps-cache-to=some-project/main --deps-cache-from=some-project/main "
            "/mount/.": "",
        },
    )
    gitlab_project.run_docker_command(
        action_docker_image_id, "python /gitlab_action/deploy.py /mount/dagster_cloud.yaml"
    )

    assert "Updating code location foo" in gitlab_project.get_stdout()
