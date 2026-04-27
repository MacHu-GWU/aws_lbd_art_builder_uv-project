# -*- coding: utf-8 -*-

"""
End-to-end test for the full Build → Package → Upload → Publish pipeline.

Uses ``moto`` to mock S3 and Lambda — no real AWS credentials needed.
Uses a real ``uv sync`` against ``examples/my_lbd_app-project``.
"""

from pathlib import Path

import boto3
from moto import mock_aws
from boto_session_manager import BotoSesManager
from s3pathlib import S3Path, context

from aws_lbd_art_builder_uv.layer.local_builder import UvLambdaLayerLocalBuilder
from aws_lbd_art_builder_uv.layer.validate import validate_artifacts

import aws_lbd_art_builder_core.api as aws_lbd_art_builder_core


dir_examples = Path(__file__).parent.parent.parent / "examples"
dir_my_lbd_app = dir_examples / "my_lbd_app-project"

LAYER_NAME = "test_layer"
AWS_REGION = "us-east-1"
S3_BUCKET = "test-artifacts-bucket"
S3_PREFIX = "projects/test_layer/lambda/"


class TestDeploymentE2E:
    @mock_aws
    def test_build_package_upload_publish(self):
        # --- Setup mock AWS ---
        bsm = BotoSesManager(region_name=AWS_REGION)
        bsm.s3_client.create_bucket(Bucket=S3_BUCKET)
        context.attach_boto_session(bsm)
        s3dir_lambda = S3Path(f"s3://{S3_BUCKET}/{S3_PREFIX}").to_dir()

        path_pyproject_toml = dir_my_lbd_app / "pyproject.toml"
        path_manifest = dir_my_lbd_app / "uv.lock"

        # --- Step 1: Build ---
        builder = UvLambdaLayerLocalBuilder(
            path_pyproject_toml=path_pyproject_toml,
            skip_prompt=True,
        )
        builder.run()

        path_layout = builder.path_layout
        dir_python = path_layout.dir_python
        path_layer_zip = path_layout.path_build_lambda_layer_zip

        # Validate artifacts
        result = validate_artifacts(
            dir_python=dir_python,
            path_pyproject_toml=path_pyproject_toml,
        )
        assert result["ok"] is True

        # --- Step 2: Package ---
        aws_lbd_art_builder_core.layer_api.create_layer_zip_file(
            dir_python=dir_python,
            path_layer_zip=path_layer_zip,
            verbose=False,
        )
        assert path_layer_zip.exists()
        assert path_layer_zip.stat().st_size > 0

        # --- Step 3: Upload ---
        aws_lbd_art_builder_core.layer_api.upload_layer_zip_to_s3(
            s3_client=bsm,
            path_pyproject_toml=path_pyproject_toml,
            s3dir_lambda=s3dir_lambda,
            path_manifest=path_manifest,
        )

        # Verify upload
        s3path_zip = s3dir_lambda.joinpath("layer", "layer.zip").to_file()
        assert s3path_zip.exists(bsm=bsm)

        # --- Step 4: Publish ---
        publisher = aws_lbd_art_builder_core.layer_api.LambdaLayerVersionPublisher(
            path_pyproject_toml=path_pyproject_toml,
            s3dir_lambda=s3dir_lambda,
            path_manifest=path_manifest,
            s3_client=bsm,
            layer_name=LAYER_NAME,
            lambda_client=bsm.lambda_client,
            publish_layer_version_kwargs={
                "CompatibleRuntimes": ["python3.12"],
                "Description": "test layer",
            },
        )
        layer_deployment = publisher.run()

        # Verify result
        assert layer_deployment.layer_name == LAYER_NAME
        assert layer_deployment.layer_version == 1
        assert "arn:aws:lambda" in layer_deployment.layer_version_arn
        assert layer_deployment.s3path_manifest.exists(bsm=bsm)


if __name__ == "__main__":
    from aws_lbd_art_builder_uv.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_uv.layer",
        is_folder=True,
        preview=False,
    )
