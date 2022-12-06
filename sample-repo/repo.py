import csv
import os

import requests
from dagster import asset, define_asset_job, job, op, repository


@asset
def cereals():
    response = requests.get("https://docs.dagster.io/assets/cereal.csv")
    lines = response.text.split("\n")
    cereal_rows = [row for row in csv.DictReader(lines)]

    return cereal_rows


@asset
def nabisco_cereals(cereals):
    """Cereals manufactured by Nabisco"""
    return [row for row in cereals if row["mfr"] == "N"]


@asset
def prha_asset():
    return 1


all_cereals_job = define_asset_job(name="all_cereals_job")


@op
def simple_op(context):
    value = os.getenv("FAKE_SECRET")
    context.log.info(f"GOT: {value}")


@job
def simple_job():
    simple_op()


# TODO: When https://github.com/dagster-io/dagster/pull/10890 merged, use this
# defs = Definitions(
#     assets=[cereals + nabisco_cereals + prha_asset], jobs=[all_cereals_job, simple_job]
# )


@repository
def __repository__():
    return [
        cereals,
        nabisco_cereals,
        prha_asset,
        all_cereals_job,
        simple_job,
    ]
