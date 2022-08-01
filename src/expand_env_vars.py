import json, os

"""
Reads a JSON blob from the "INPUT_ENV_VARS" env var and decomposes it, creating a template file of
Docker commands to bake env vars into the built image.
"""

OUTPUT_FILE_NAME = "Dockerfile.envvars.template"
INPUT_ENV_VAR_NAME = "INPUT_ENV_VARS"

def main():
    with open(OUTPUT_FILE_NAME, mode="w") as f:
        ev_json = os.getenv(INPUT_ENV_VAR_NAME)
        if ev_json:
            for k, v in json.loads(ev_json).items():
                f.write(f"ENV {k}={v}\n")
    print(OUTPUT_FILE_NAME)


if __name__ == "__main__":
    main()
