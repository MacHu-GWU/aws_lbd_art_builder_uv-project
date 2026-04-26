# -*- coding: utf-8 -*-

import pytest
from pathlib import Path

from aws_lbd_art_builder_uv.layer.builder import (
    UvLambdaLayerLocalBuilder,
    UvLambdaLayerContainerBuilder,
)


class TestUvLambdaLayerLocalBuilder:
    def test_instantiation(self, tmp_path):
        p = tmp_path / "pyproject.toml"
        p.write_text("[project]\nname = 'test'\nversion = '0.1.0'\n")
        builder = UvLambdaLayerLocalBuilder(
            path_pyproject_toml=p,
            skip_prompt=True,
        )
        assert builder.path_bin_uv is None
        assert builder.path_layout.dir_project_root == tmp_path

    def test_instantiation_with_custom_uv_path(self, tmp_path):
        p = tmp_path / "pyproject.toml"
        p.write_text("[project]\nname = 'test'\nversion = '0.1.0'\n")
        uv_path = Path("/usr/local/bin/uv")
        builder = UvLambdaLayerLocalBuilder(
            path_pyproject_toml=p,
            path_bin_uv=uv_path,
            skip_prompt=True,
        )
        assert builder.path_bin_uv == uv_path

    def test_step_1_1_print_info(self, tmp_path):
        p = tmp_path / "pyproject.toml"
        p.write_text("[project]\nname = 'test'\nversion = '0.1.0'\n")
        logs = []
        builder = UvLambdaLayerLocalBuilder(
            path_pyproject_toml=p,
            skip_prompt=True,
            printer=logs.append,
        )
        builder.step_1_1_print_info()
        log_text = "\n".join(logs)
        assert "path_bin_uv" in log_text


class TestUvLambdaLayerContainerBuilder:
    def test_default_path_script(self):
        from aws_lbd_art_builder_uv.paths import path_enum

        p = Path("/tmp/pyproject.toml")
        builder = UvLambdaLayerContainerBuilder(
            path_pyproject_toml=p,
            py_ver_major=3,
            py_ver_minor=12,
            is_arm=False,
        )
        assert builder.path_script == path_enum.path_build_in_container_script

    def test_preflight_check_raises_when_uv_lock_missing(self, tmp_path):
        p = tmp_path / "pyproject.toml"
        p.write_text("[project]\nname = 'test'\nversion = '0.1.0'\n")
        builder = UvLambdaLayerContainerBuilder(
            path_pyproject_toml=p,
            py_ver_major=3,
            py_ver_minor=12,
            is_arm=False,
        )
        with pytest.raises(FileNotFoundError, match="UV lock file not found"):
            builder.step_1_preflight_check()

    def test_preflight_check_passes_when_uv_lock_exists(self, tmp_path):
        p = tmp_path / "pyproject.toml"
        p.write_text("[project]\nname = 'test'\nversion = '0.1.0'\n")
        (tmp_path / "uv.lock").write_text("# lock file")
        builder = UvLambdaLayerContainerBuilder(
            path_pyproject_toml=p,
            py_ver_major=3,
            py_ver_minor=12,
            is_arm=False,
        )
        # Should not raise
        builder.step_1_preflight_check()

    def test_image_uri_x86(self, tmp_path):
        p = tmp_path / "pyproject.toml"
        p.write_text("[project]\nname = 'test'\nversion = '0.1.0'\n")
        builder = UvLambdaLayerContainerBuilder(
            path_pyproject_toml=p,
            py_ver_major=3,
            py_ver_minor=12,
            is_arm=False,
        )
        assert "build-python3.12" in builder.image_uri
        assert "x86_64" in builder.image_uri

    def test_image_uri_arm(self, tmp_path):
        p = tmp_path / "pyproject.toml"
        p.write_text("[project]\nname = 'test'\nversion = '0.1.0'\n")
        builder = UvLambdaLayerContainerBuilder(
            path_pyproject_toml=p,
            py_ver_major=3,
            py_ver_minor=12,
            is_arm=True,
        )
        assert "arm64" in builder.image_uri


if __name__ == "__main__":
    from aws_lbd_art_builder_uv.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_uv.layer.builder",
        preview=False,
    )
