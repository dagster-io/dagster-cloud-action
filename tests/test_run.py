def test_run_without_wait(tmp_path, exec_context, action_docker_image_id):
    """Test the run script without wait flag (default behavior)."""
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
            "INPUT_WAIT": "false",  # Explicitly set to false
            "GITHUB_OUTPUT": output_file.name,
        }
    )

    exec_context.stub_command(
        "dagster-cloud",
        {
            "job launch --url http://dagster.cloud/test "
            "--deployment prod "
            "--api-token api-token "
            "--location some-location "
            "--repository some-repository "
            "--job some-job "
            "--tags some-tags "
            "--config-json some-config-json": "ee1ecc27-1dbe-435d-bd62-c2b1c491eef6",
        },
    )
    exec_context.run_docker_command(action_docker_image_id, "/run.sh")
    stdout = exec_context.get_stdout()
    
    assert "Successfully launched run: ee1ecc27-1dbe-435d-bd62-c2b1c491eef6" in stdout
    assert "run_id=ee1ecc27-1dbe-435d-bd62-c2b1c491eef6" in output_file.read_text()


def test_run_with_wait_true(tmp_path, exec_context, action_docker_image_id):
    """Test the run script with wait flag enabled."""
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
            "INPUT_WAIT": "true",
            "GITHUB_OUTPUT": output_file.name,
        }
    )

    # Mock the multi-line output that dagster-cloud CLI produces with --wait
    multi_line_output = """Run ee1ecc27-1dbe-435d-bd62-c2b1c491eef6 is in progress (status: STARTING)...
Run ee1ecc27-1dbe-435d-bd62-c2b1c491eef6 is in progress (status: STARTED)...
Run ee1ecc27-1dbe-435d-bd62-c2b1c491eef6 is in progress (status: STARTED)...
Run ee1ecc27-1dbe-435d-bd62-c2b1c491eef6 finished successfully."""

    exec_context.stub_command(
        "dagster-cloud",
        {
            "job launch --url http://dagster.cloud/test "
            "--deployment prod "
            "--api-token api-token "
            "--location some-location "
            "--repository some-repository "
            "--job some-job "
            "--tags some-tags "
            "--config-json some-config-json "
            "--wait": multi_line_output,
        },
    )
    exec_context.run_docker_command(action_docker_image_id, "/run.sh")
    stdout = exec_context.get_stdout()
    
    assert "Successfully launched run: ee1ecc27-1dbe-435d-bd62-c2b1c491eef6" in stdout
    assert "run_id=ee1ecc27-1dbe-435d-bd62-c2b1c491eef6" in output_file.read_text()


def test_run_with_wait_various_values(tmp_path, exec_context, action_docker_image_id):
    """Test that various truthy values for wait parameter work."""
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
            "INPUT_WAIT": "TRUE",  # Test uppercase
            "GITHUB_OUTPUT": output_file.name,
        }
    )

    exec_context.stub_command(
        "dagster-cloud",
        {
            "job launch --url http://dagster.cloud/test "
            "--deployment prod "
            "--api-token api-token "
            "--location some-location "
            "--repository some-repository "
            "--job some-job "
            "--tags some-tags "
            "--config-json some-config-json "
            "--wait": "Run ee1ecc27-1dbe-435d-bd62-c2b1c491eef6 finished successfully.",
        },
    )
    exec_context.run_docker_command(action_docker_image_id, "/run.sh")
    stdout = exec_context.get_stdout()
    
    assert "Successfully launched run: ee1ecc27-1dbe-435d-bd62-c2b1c491eef6" in stdout
    assert "run_id=ee1ecc27-1dbe-435d-bd62-c2b1c491eef6" in output_file.read_text()


def test_run_legacy_compatibility(tmp_path, exec_context, action_docker_image_id):
    """Test backwards compatibility when INPUT_WAIT is not set."""
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
            # Note: No INPUT_WAIT set
            "GITHUB_OUTPUT": output_file.name,
        }
    )

    exec_context.stub_command(
        "dagster-cloud",
        {
            "job launch --url http://dagster.cloud/test "
            "--deployment prod "
            "--api-token api-token "
            "--location some-location "
            "--repository some-repository "
            "--job some-job "
            "--tags some-tags "
            "--config-json some-config-json": "ee1ecc27-1dbe-435d-bd62-c2b1c491eef6",
        },
    )
    exec_context.run_docker_command(action_docker_image_id, "/run.sh")
    stdout = exec_context.get_stdout()
    
    assert "Successfully launched run: ee1ecc27-1dbe-435d-bd62-c2b1c491eef6" in stdout
    assert "run_id=ee1ecc27-1dbe-435d-bd62-c2b1c491eef6" in output_file.read_text()


def test_run_with_wait_and_interval(tmp_path, exec_context, action_docker_image_id):
    """Test the run script with wait and interval flags enabled."""
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
            "INPUT_WAIT": "true",
            "INPUT_INTERVAL": "10",
            "GITHUB_OUTPUT": output_file.name,
        }
    )

    # Mock the multi-line output that dagster-cloud CLI produces with --wait --interval
    multi_line_output = """Run ee1ecc27-1dbe-435d-bd62-c2b1c491eef6 is in progress (status: STARTING)...
Run ee1ecc27-1dbe-435d-bd62-c2b1c491eef6 is in progress (status: STARTED)...
Run ee1ecc27-1dbe-435d-bd62-c2b1c491eef6 finished successfully."""

    exec_context.stub_command(
        "dagster-cloud",
        {
            "job launch --url http://dagster.cloud/test "
            "--deployment prod "
            "--api-token api-token "
            "--location some-location "
            "--repository some-repository "
            "--job some-job "
            "--tags some-tags "
            "--config-json some-config-json "
            "--wait "
            "--interval 10": multi_line_output,
        },
    )
    exec_context.run_docker_command(action_docker_image_id, "/run.sh")
    stdout = exec_context.get_stdout()
    
    assert "Successfully launched run: ee1ecc27-1dbe-435d-bd62-c2b1c491eef6" in stdout
    assert "run_id=ee1ecc27-1dbe-435d-bd62-c2b1c491eef6" in output_file.read_text()


def test_run_with_wait_no_interval(tmp_path, exec_context, action_docker_image_id):
    """Test the run script with wait enabled but no interval specified."""
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
            "INPUT_WAIT": "true",
            # Note: No INPUT_INTERVAL set
            "GITHUB_OUTPUT": output_file.name,
        }
    )

    # Mock the multi-line output that dagster-cloud CLI produces with --wait (no interval)
    multi_line_output = """Run ee1ecc27-1dbe-435d-bd62-c2b1c491eef6 is in progress (status: STARTING)...
Run ee1ecc27-1dbe-435d-bd62-c2b1c491eef6 is in progress (status: STARTED)...
Run ee1ecc27-1dbe-435d-bd62-c2b1c491eef6 finished successfully."""

    exec_context.stub_command(
        "dagster-cloud",
        {
            "job launch --url http://dagster.cloud/test "
            "--deployment prod "
            "--api-token api-token "
            "--location some-location "
            "--repository some-repository "
            "--job some-job "
            "--tags some-tags "
            "--config-json some-config-json "
            "--wait": multi_line_output,
        },
    )
    exec_context.run_docker_command(action_docker_image_id, "/run.sh")
    stdout = exec_context.get_stdout()
    
    assert "Successfully launched run: ee1ecc27-1dbe-435d-bd62-c2b1c491eef6" in stdout
    assert "run_id=ee1ecc27-1dbe-435d-bd62-c2b1c491eef6" in output_file.read_text()


def test_run_interval_without_wait_fails(tmp_path, exec_context, action_docker_image_id):
    """Test that using interval without wait fails with error."""
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
            "INPUT_WAIT": "false",
            "INPUT_INTERVAL": "10",  # This should cause an error
            "GITHUB_OUTPUT": output_file.name,
        }
    )

    # No need to stub command since it should fail before calling dagster-cloud
    try:
        exec_context.run_docker_command(action_docker_image_id, "/run.sh")
        assert False, "Expected command to fail"
    except ValueError:
        # Check that the error contains our expected message
        stdout = exec_context.get_stdout()
        assert "ERROR: interval parameter can only be used when wait is true" in stdout


# Keep the original test for backwards compatibility
def test_run(tmp_path, exec_context, action_docker_image_id):
    """Original test maintained for backwards compatibility."""
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
            "job launch --url http://dagster.cloud/test "
            "--deployment prod "
            "--api-token api-token "
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
