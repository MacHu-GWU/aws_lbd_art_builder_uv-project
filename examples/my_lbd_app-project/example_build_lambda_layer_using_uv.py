# -*- coding: utf-8 -*-

from pathlib import Path
from boto_session_manager import BotoSesManager
from s3pathlib import S3Path

from aws_lbd_art_builder_uv import api as aws_lbd_art_builder_uv

bsm = BotoSesManager(profile_name="eas_app_dev_us_east_1")
bucket = f"{bsm.aws_account_alias}-{bsm.aws_region}-artifacts"
prefix = "projects/aws_lbd_art_builder_uv/"
s3dir_root = S3Path(f"s3://{bucket}/{prefix}").to_dir()
dir_project_root = Path(__file__).parent
dir_lambda_build_layer = dir_project_root / "build" / "lambda" / "layer"
