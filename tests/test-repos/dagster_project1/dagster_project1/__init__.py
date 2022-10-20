from dagster import AssetSelection, asset, define_asset_job, repository


@asset
def asset_1():
    return ["some", "test", "data"]


@repository
def repo():
    return [
        asset_1,
        define_asset_job("job_1", selection=AssetSelection.assets(asset_1)),
    ]
