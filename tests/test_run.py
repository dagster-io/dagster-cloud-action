import json

def test_run(tmp_path, exec_context, action_docker_image_id):
    output_file = tmp_path / "output.txt"
    output_file.touch()

    exec_context.set_env(
        {
            "GITHUB_ACTIONS": "true",
            "DAGSTER_CLOUD_URL": "http://dagster.cloud/test",
            "INPUT_DEPLOYMENT": "prod",
            "DAGSTER_CLOUD_API_TOKEN": "api-token",
            "INPUT_LOCATION_NAME": "some-location",
            "INPUT_REPOSITORY_NAME": "some-repository",
            "INPUT_JOB_NAME": "some-job",
            "INPUT_TAGS_JSON": "some-tags",
            "INPUT_CONFIG_JSON": "some-config-json",
            "GITHUB_OUTPUT": output_file.name,
        }
    )

    exec_context.stub_command(
        "dagster-cloud",
        {
            "job launch --url http://dagster.cloud/test/prod "
            "--api-token api-token  "
            "--location some-location "
            "--repository some-repository "
            "--job some-job "
            "--tags some-tags "
            "--config-json some-config-json": "some-run",
        },
    )
    exec_context.run_docker_command(action_docker_image_id, "/run.sh")
    assert "Successfully launched run: some-run" in exec_context.get_stdout()
    assert "run_id=some-run" in output_file.read_text()
