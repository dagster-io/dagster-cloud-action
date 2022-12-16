import logging
from dagster_cloud_cli.core.pex_builder import deploy

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    deploy.cli()
