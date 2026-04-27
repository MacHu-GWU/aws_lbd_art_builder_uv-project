# -*- coding: utf-8 -*-

"""
Unit tests for :mod:`aws_lbd_art_builder_uv.layer.validate`.

Uses synthetic fixture directories — no uv, Docker, or AWS needed.
"""

import pytest
from pathlib import Path

from aws_lbd_art_builder_uv.layer.validate import (
    _normalize,
    _strip_version_spec,
    _find_dist_info,
    _read_wheel_tags,
    _is_linux_compatible,
    validate_artifacts,
)


# ---------------------------------------------------------------------------
# Helper: create a fake dist-info with a WHEEL file
# ---------------------------------------------------------------------------
def _make_dist_info(dir_python: Path, name: str, version: str, tag: str):
    """Create a minimal ``{name}-{version}.dist-info/WHEEL`` fixture."""
    dist_info = dir_python / f"{name}-{version}.dist-info"
    dist_info.mkdir(parents=True, exist_ok=True)
    wheel = dist_info / "WHEEL"
    wheel.write_text(
        f"Wheel-Version: 1.0\n"
        f"Generator: test\n"
        f"Root-Is-Purelib: true\n"
        f"Tag: {tag}\n"
    )
    return dist_info


def _make_pyproject_toml(tmp_path: Path, deps: list[str]) -> Path:
    """Create a minimal ``pyproject.toml`` with the given dependencies."""
    lines = ",\n".join(f'    "{d}"' for d in deps)
    content = (
        "[project]\n"
        'name = "test-project"\n'
        'version = "0.1.0"\n'
        f"dependencies = [\n{lines}\n]\n"
    )
    p = tmp_path / "pyproject.toml"
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# Tests for internal helpers
# ---------------------------------------------------------------------------
class TestNormalize:
    def test_underscores(self):
        assert _normalize("my_package") == "my-package"

    def test_dots(self):
        assert _normalize("my.package") == "my-package"

    def test_mixed_case(self):
        assert _normalize("My-Package") == "my-package"

    def test_consecutive_separators(self):
        assert _normalize("my__package") == "my-package"


class TestStripVersionSpec:
    def test_no_version(self):
        assert _strip_version_spec("boto3") == "boto3"

    def test_version_range(self):
        assert _strip_version_spec("boto3>=1.28,<2") == "boto3"

    def test_extras(self):
        assert _strip_version_spec("pkg[extra]>=1.0") == "pkg"

    def test_spaces(self):
        assert _strip_version_spec("boto3 >=1.0") == "boto3"


class TestFindDistInfo:
    def test_found(self, tmp_path):
        dir_python = tmp_path / "python"
        dir_python.mkdir()
        _make_dist_info(dir_python, "boto3", "1.28.0", "py3-none-any")
        result = _find_dist_info(dir_python, "boto3")
        assert result is not None
        assert result.name == "boto3-1.28.0.dist-info"

    def test_normalized_name(self, tmp_path):
        dir_python = tmp_path / "python"
        dir_python.mkdir()
        _make_dist_info(dir_python, "my_package", "0.1.0", "py3-none-any")
        result = _find_dist_info(dir_python, "my-package")
        assert result is not None

    def test_not_found(self, tmp_path):
        dir_python = tmp_path / "python"
        dir_python.mkdir()
        result = _find_dist_info(dir_python, "nonexistent")
        assert result is None


class TestReadWheelTags:
    def test_reads_tags(self, tmp_path):
        dist_info = _make_dist_info(tmp_path, "pkg", "1.0", "py3-none-any")
        tags = _read_wheel_tags(dist_info)
        assert tags == ["py3-none-any"]

    def test_no_wheel_file(self, tmp_path):
        dist_info = tmp_path / "pkg-1.0.dist-info"
        dist_info.mkdir()
        tags = _read_wheel_tags(dist_info)
        assert tags == []


class TestIsLinuxCompatible:
    def test_pure_python(self):
        assert _is_linux_compatible(["py3-none-any"]) is None

    def test_linux(self):
        assert _is_linux_compatible(["cp312-cp312-manylinux_2_17_x86_64"]) is True

    def test_macos(self):
        assert _is_linux_compatible(["cp312-cp312-macosx_14_0_arm64"]) is False

    def test_empty(self):
        assert _is_linux_compatible([]) is None

    def test_musllinux(self):
        assert _is_linux_compatible(["cp312-cp312-musllinux_1_2_x86_64"]) is True


# ---------------------------------------------------------------------------
# Tests for validate_artifacts
# ---------------------------------------------------------------------------
class TestValidateArtifacts:
    def test_all_found_pure_python(self, tmp_path):
        dir_python = tmp_path / "python"
        dir_python.mkdir()
        _make_dist_info(dir_python, "boto3", "1.28.0", "py3-none-any")
        _make_dist_info(dir_python, "requests", "2.31.0", "py3-none-any")
        path_toml = _make_pyproject_toml(tmp_path, ["boto3", "requests>=2.0"])

        result = validate_artifacts(dir_python, path_toml)
        assert result["ok"] is True
        assert len(result["packages"]) == 2
        assert all(p["found"] for p in result["packages"])

    def test_missing_package(self, tmp_path):
        dir_python = tmp_path / "python"
        dir_python.mkdir()
        _make_dist_info(dir_python, "boto3", "1.28.0", "py3-none-any")
        path_toml = _make_pyproject_toml(tmp_path, ["boto3", "missing-pkg"])

        with pytest.raises(AssertionError, match="missing-pkg"):
            validate_artifacts(dir_python, path_toml)

    def test_check_linux_pass(self, tmp_path):
        dir_python = tmp_path / "python"
        dir_python.mkdir()
        _make_dist_info(
            dir_python, "numpy", "1.26.0", "cp312-cp312-manylinux_2_17_x86_64"
        )
        path_toml = _make_pyproject_toml(tmp_path, ["numpy"])

        result = validate_artifacts(dir_python, path_toml, check_linux=True)
        assert result["ok"] is True
        assert result["packages"][0]["linux"] is True

    def test_check_linux_fail_macos(self, tmp_path):
        dir_python = tmp_path / "python"
        dir_python.mkdir()
        _make_dist_info(
            dir_python, "numpy", "1.26.0", "cp312-cp312-macosx_14_0_arm64"
        )
        path_toml = _make_pyproject_toml(tmp_path, ["numpy"])

        with pytest.raises(AssertionError, match="non-Linux"):
            validate_artifacts(dir_python, path_toml, check_linux=True)

    def test_check_linux_pure_python_ok(self, tmp_path):
        """Pure Python packages should pass check_linux — they work everywhere."""
        dir_python = tmp_path / "python"
        dir_python.mkdir()
        _make_dist_info(dir_python, "boto3", "1.28.0", "py3-none-any")
        path_toml = _make_pyproject_toml(tmp_path, ["boto3"])

        result = validate_artifacts(dir_python, path_toml, check_linux=True)
        assert result["ok"] is True

    def test_no_dependencies(self, tmp_path):
        dir_python = tmp_path / "python"
        dir_python.mkdir()
        path_toml = _make_pyproject_toml(tmp_path, [])

        result = validate_artifacts(dir_python, path_toml)
        assert result["ok"] is True
        assert len(result["packages"]) == 0


if __name__ == "__main__":
    from aws_lbd_art_builder_uv.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_uv.layer.validate",
        preview=False,
    )
