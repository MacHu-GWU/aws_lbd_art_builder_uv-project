# -*- coding: utf-8 -*-

"""
Unit tests for :mod:`aws_lbd_art_builder_uv.layer.uv_sync_options`.

Pure argument rendering — no uv, Docker, or AWS needed.
"""

import pytest

from aws_lbd_art_builder_uv.layer.uv_sync_options import UvSyncOptions


class TestUvSyncOptions:
    def test_default_is_minimal(self):
        # The default must stay "dependencies only, no dev group", because
        # that is what every existing caller already gets today.
        assert UvSyncOptions().to_args() == ["--no-dev"]

    def test_multiple_extras(self):
        opts = UvSyncOptions(extras=["aws", "web"])
        assert opts.to_args() == [
            "--no-dev",
            "--extra",
            "aws",
            "--extra",
            "web",
        ]

    def test_all_extras_with_exclusion(self):
        opts = UvSyncOptions(all_extras=True, no_extras=["dev-tools"])
        assert opts.to_args() == [
            "--no-dev",
            "--all-extras",
            "--no-extra",
            "dev-tools",
        ]

    def test_groups(self):
        opts = UvSyncOptions(
            groups=["prod"],
            no_groups=["docs"],
            no_default_groups=True,
        )
        assert opts.to_args() == [
            "--no-dev",
            "--no-default-groups",
            "--group",
            "prod",
            "--no-group",
            "docs",
        ]

    def test_all_groups(self):
        assert UvSyncOptions(all_groups=True, no_dev=False).to_args() == [
            "--all-groups",
        ]

    def test_keep_dev(self):
        assert UvSyncOptions(no_dev=False).to_args() == []

    def test_extras_and_all_extras_conflict(self):
        with pytest.raises(ValueError):
            UvSyncOptions(extras=["aws"], all_extras=True)

    def test_no_extras_without_all_extras(self):
        with pytest.raises(ValueError):
            UvSyncOptions(no_extras=["aws"])


if __name__ == "__main__":
    from aws_lbd_art_builder_uv.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_uv.layer.uv_sync_options",
        preview=False,
    )
