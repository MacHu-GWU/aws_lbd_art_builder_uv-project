# -*- coding: utf-8 -*-

"""
Example: Build Lambda layer using uv on local machine.

Usage::

    cd examples/my_lbd_app-project
    .venv/bin/python example_build_lambda_layer_using_uv_in_local.py
"""

from pathlib import Path
from aws_lbd_art_builder_uv.api import layer

dir_project_root = Path(__file__).parent

builder = layer.UvLambdaLayerLocalBuilder(
    path_pyproject_toml=dir_project_root / "pyproject.toml",
    skip_prompt=True,
)

# Run the workflow in one line
builder.run()

# or run step by step
# builder.step_1_preflight_check()
# builder.step_2_prepare_environment()
# builder.step_3_execute_build()
# builder.step_4_finalize_artifacts()
