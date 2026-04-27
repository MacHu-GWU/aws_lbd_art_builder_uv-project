# -*- coding: utf-8 -*-

"""
End-to-end test for :class:`UvLambdaLayerLocalBuilder`.

Runs a real ``uv sync`` using the ``examples/my_lbd_app-project`` fixture,
then validates the output with :func:`validate_artifacts`.

Requires ``uv`` to be installed on the host.
"""

from pathlib import Path

from aws_lbd_art_builder_uv.layer.local_builder import UvLambdaLayerLocalBuilder
from aws_lbd_art_builder_uv.layer.validate import validate_artifacts


dir_examples = Path(__file__).parent.parent.parent / "examples"
dir_my_lbd_app = dir_examples / "my_lbd_app-project"


class TestLocalBuilderE2E:
    def test_build_and_validate(self):
        path_pyproject_toml = dir_my_lbd_app / "pyproject.toml"

        builder = UvLambdaLayerLocalBuilder(
            path_pyproject_toml=path_pyproject_toml,
            skip_prompt=True,
        )
        builder.run()

        result = validate_artifacts(
            dir_python=builder.path_layout.dir_python,
            path_pyproject_toml=path_pyproject_toml,
        )
        assert result["ok"] is True
        assert len(result["packages"]) > 0


if __name__ == "__main__":
    from aws_lbd_art_builder_uv.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_uv.layer.local_builder",
        preview=False,
    )
