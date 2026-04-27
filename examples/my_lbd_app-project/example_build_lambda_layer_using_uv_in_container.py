# -*- coding: utf-8 -*-

"""
Example: Build Lambda layer using uv inside a Docker container.

Usage::

    cd examples/my_lbd_app-project
    .venv/bin/python example_build_lambda_layer_using_uv_in_container.py

For development testing (install from GitHub instead of PyPI)::

    cd examples/my_lbd_app-project
    .venv/bin/python example_build_lambda_layer_using_uv_in_container.py --dev
"""

import sys
from pathlib import Path
from aws_lbd_art_builder_uv.api import layer

dir_project_root = Path(__file__).parent

# For development testing, install from GitHub main branch
if "--dev" in sys.argv:
    lib_install_spec = (
        "aws_lbd_art_builder_uv @ "
        "git+https://github.com/MacHu-GWU/aws_lbd_art_builder_uv-project.git@main"
    )
else:
    lib_install_spec = "aws_lbd_art_builder_uv>=0.1.1,<1.0.0"

builder = layer.UvLambdaLayerContainerBuilder(
    path_pyproject_toml=dir_project_root / "pyproject.toml",
    py_ver_major=3,
    py_ver_minor=12,
    is_arm=False,
    lib_install_spec=lib_install_spec,
)

# Run the workflow in one line
builder.run()

# or run step by step
# builder.step_1_preflight_check()
# builder.step_2_prepare_environment()
# builder.step_3_execute_build()
# builder.step_4_finalize_artifacts()
