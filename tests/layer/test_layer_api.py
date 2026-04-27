# -*- coding: utf-8 -*-

from aws_lbd_art_builder_uv.layer import api


def test_layer_api_imports():
    _ = api
    _ = api.UvLambdaLayerLocalBuilder
    _ = api.UvLambdaLayerContainerBuilder
    _ = api.Credentials
    _ = api.LayerPathLayout
    _ = api.LayerS3Layout
    _ = api.move_to_dir_python
    _ = api.default_ignore_package_list
    _ = api.create_layer_zip_file
    _ = api.upload_layer_zip_to_s3
    _ = api.LambdaLayerVersionPublisher
    _ = api.LayerDeployment
    _ = api.validate_artifacts


if __name__ == "__main__":
    from aws_lbd_art_builder_uv.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_uv.layer.api",
        preview=False,
    )
