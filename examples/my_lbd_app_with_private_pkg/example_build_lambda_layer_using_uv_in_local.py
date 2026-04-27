# -*- coding: utf-8 -*-

"""
Example: Build Lambda layer using uv on local machine.

Usage::

    cd examples/my_lbd_app_with_private_pkg
    .venv/bin/python example_build_lambda_layer_using_uv_in_local.py
"""

from example_settings import settings
import aws_lbd_art_builder_uv.api as aws_lbd_art_builder_uv

builder = aws_lbd_art_builder_uv.layer_api.UvLambdaLayerLocalBuilder(
    path_pyproject_toml=settings.path_pyproject_toml,
    credentials=settings.credentials,
    skip_prompt=True,
)

# Run the workflow in one line
# builder.run()

# or run step by step
builder.step_1_preflight_check()
builder.step_2_prepare_environment()
builder.step_3_execute_build()
builder.step_4_finalize_artifacts()

# Validate artifacts
aws_lbd_art_builder_uv.layer_api.validate_artifacts(
    dir_python=builder.path_layout.dir_python,
    path_pyproject_toml=settings.path_pyproject_toml,
)
