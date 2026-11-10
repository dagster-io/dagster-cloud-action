import pytest


@pytest.mark.parametrize(
    "env, expected_from",
    [
        ({}, "FROM python:3.14-slim"),
        ({"INPUT_BASE_IMAGE": "my-image:1"}, "FROM python:3.14-slim"),
        (
            {"INPUT_BASE_IMAGE": "my-image:1", "CUSTOM_BASE_IMAGE_ALLOWED": "1"},
            "FROM my-image:1",
        ),
    ],
)
def test_copy_template_base_image(exec_context, action_docker_image_id, env, expected_from):
    exec_context.set_env({"INPUT_TARGET_DIRECTORY": "/mount", **env})
    exec_context.run_docker_command(action_docker_image_id, "/copy_template.sh")

    dockerfile = exec_context.tmp_file_content("Dockerfile")
    assert dockerfile.splitlines()[0] == expected_from
