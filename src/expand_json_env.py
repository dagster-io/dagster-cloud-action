import json, os

"""
Reads a JSON blob from the "INPUT_LOCATION" env var and decomposes it,
creating a `source`-able environment file which sets the value
associated with each top-level key to "LOCATION_{KEY}" env vars.

e.g.
{
    name: "my-location",
    build_folder: "test"
}

produces

LOCATION_NAME=my-location
LOCATION_BUILD_FOLDER=test
"""

OUTPUT_FILE_NAME = "json_env"
INPUT_ENV_VAR_NAME = "INPUT_LOCATION"
OUTPUT_ENV_VAR_PREFIX = "INPUT_"


def main():
    with open(OUTPUT_FILE_NAME, mode="w") as f:
        input_location = os.getenv(INPUT_ENV_VAR_NAME)
        if input_location:
            for k, v in json.loads(os.getenv(INPUT_ENV_VAR_NAME)).items():
                output_env_var_name = f"{OUTPUT_ENV_VAR_PREFIX}{k.upper()}"
                if not os.getenv(output_env_var_name):
                    f.write(f"{output_env_var_name}={v}\n")
    print(OUTPUT_FILE_NAME)


if __name__ == "__main__":
    main()
