def test_registry_info(exec_context, action_docker_image_id):
    exec_context.set_env(
        {
            "DAGSTER_CLOUD_URL": "http://dagster.cloud/test",
            "INPUT_DEPLOYMENT": "prod",
            "DAGSTER_CLOUD_API_TOKEN": "api-token",
            "GITHUB_ENV": exec_context.tmp_file_path("github.env"),
        }
    )

    exec_context.stub_command(
        "dagster-cloud",
        {
            "serverless registry-info --url http://dagster.cloud/test/prod --api-token api-token": "AWS_ECR_USERNAME=aws-username\nAWS_ECR_PASSWORD=pw\nAWS_DEFAULT_REGION=region\nREGISTRY_URL=http://reg-url\n"
        },
    )
    exec_context.run_docker_command(action_docker_image_id, "/registry_info.sh")
    assert "Loaded registry" in exec_context.get_stdout()

    github_env = dict(
        line.strip().split("=", 1)
        for line in exec_context.tmp_file_content("github.env").splitlines()
    )
    assert github_env["AWS_ECR_USERNAME"] == "aws-username"
    assert github_env["AWS_ECR_PASSWORD"] == "pw"
    assert github_env["AWS_DEFAULT_REGION"] == "region"
    assert github_env["REGISTRY_URL"] == "http://reg-url"
