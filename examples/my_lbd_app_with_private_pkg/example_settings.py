# -*- coding: utf-8 -*-

"""
Example settings for Lambda layer builds with private repository credentials.

This module centralises build configuration (Python version, architecture,
AWS profile) and lazy-loads CodeArtifact credentials when needed.

Usage::

    from example_settings import settings
    builder = UvLambdaLayerLocalBuilder(
        path_pyproject_toml=settings.path_pyproject_toml,
        credentials=settings.credentials,
        ...
    )
"""

import os
import shutil
import dataclasses
from pathlib import Path
from functools import cached_property

# ---------------------------------------------------------------------------
# Copy aws_lbd_art_builder_uv source into this example project so we can
# import it without installing the package.
# ---------------------------------------------------------------------------
dir_here = Path(__file__).absolute().parent

package_name = "aws_lbd_art_builder_uv"
dir_source = dir_here.parent.parent / package_name
dir_target = dir_here / package_name
print(f"copy from {dir_source} to {dir_target} ...")
shutil.rmtree(dir_target, ignore_errors=True)
shutil.copytree(dir_source, dir_target)

import aws_lbd_art_builder_uv.api as aws_lbd_art_builder_uv


@dataclasses.dataclass
class Settings:
    layer_name: str = dataclasses.field()
    py_ver_major: int = dataclasses.field()
    py_ver_minor: int = dataclasses.field()
    is_arm: bool = dataclasses.field()
    aws_profile: str = dataclasses.field()
    aws_region: str = dataclasses.field()
    private_index_name: str | None = dataclasses.field(default=None)

    @property
    def path_pyproject_toml(self) -> Path:
        return dir_here / "pyproject.toml"

    @property
    def path_bin_uv(self) -> Path:
        return Path("uv")

    @cached_property
    def bsm(self):
        from boto_session_manager import BotoSesManager

        return BotoSesManager(
            profile_name=self.aws_profile,
            region_name=self.aws_region,
        )

    @cached_property
    def credentials(self) -> "aws_lbd_art_builder_uv.layer_api.Credentials | None":
        if self.private_index_name is None:
            return None

        from boto_session_manager import BotoSesManager

        bsm = BotoSesManager(
            profile_name=os.environ["AWS_CODEARTIFACT_PROFILE"],
            region_name=os.environ["AWS_CODEARTIFACT_REGION"],
        )
        domain = os.environ["AWS_CODEARTIFACT_DOMAIN"]
        repository = os.environ["AWS_CODEARTIFACT_REPO"]

        res = bsm.codeartifact_client.get_repository_endpoint(
            domain=domain,
            repository=repository,
            format="pypi",
        )
        index_url = res["repositoryEndpoint"]

        res = bsm.codeartifact_client.get_authorization_token(
            domain=domain,
            durationSeconds=15 * 60,
        )
        password = res["authorizationToken"]

        return aws_lbd_art_builder_uv.layer_api.Credentials(
            index_name=self.private_index_name,
            index_url=index_url,
            username="aws",
            password=password,
        )


settings = Settings(
    layer_name="my_lbd_app_with_private_pkg",
    py_ver_major=3,
    py_ver_minor=12,
    is_arm=False,
    aws_profile="esc_app_dev_us_east_1",
    aws_region="us-east-1",
    private_index_name="esc",
    # Set to None to disable private repository credentials:
    # private_index_name=None,
)
