# -*- coding: utf-8 -*-

"""
Example: Build Lambda layer using uv inside a Docker container.

Usage::

    cd examples/my_lbd_app_with_private_pkg
    .venv/bin/python example_build_lambda_layer_using_uv_in_container.py
"""

from example_settings import settings
import aws_lbd_art_builder_uv.api as aws_lbd_art_builder_uv

builder = aws_lbd_art_builder_uv.layer_api.UvLambdaLayerContainerBuilder(
    path_pyproject_toml=settings.path_pyproject_toml,
    py_ver_major=settings.py_ver_major,
    py_ver_minor=settings.py_ver_minor,
    is_arm=settings.is_arm,
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
