# -*- coding: utf-8 -*-

"""
Example: Build Lambda layer using uv on local machine.

Usage::

    cd examples/my_lbd_app-project
    .venv/bin/python example_build_lambda_layer_using_uv_in_local.py
"""

import shutil
from pathlib import Path

dir_project_root = Path(__file__).parent

# Why copy the package source into the example project?
# These examples are standalone projects with their own pyproject.toml and
# uv.lock.  They can't "pip install" the parent package because the whole
# point is to test the *development* version of the builder code, not a
# released version.  Copying the source makes the latest code importable
# from this project's namespace without modifying sys.path or installing
# in editable mode (which would require the example project to declare
# the dependency).  The rmtree + copytree ensures a clean, up-to-date copy.
package_name = "aws_lbd_art_builder_uv"
dir_source = dir_project_root.parent.parent / package_name
dir_target = dir_project_root / package_name
print(f"copy from {dir_source} to {dir_target} ...")
shutil.rmtree(dir_target, ignore_errors=True)
shutil.copytree(dir_source, dir_target)

import aws_lbd_art_builder_uv.api as aws_lbd_art_builder_uv

builder = aws_lbd_art_builder_uv.layer_api.UvLambdaLayerLocalBuilder(
    path_pyproject_toml=dir_project_root / "pyproject.toml",
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
    path_pyproject_toml=builder.path_layout.path_pyproject_toml,
)
