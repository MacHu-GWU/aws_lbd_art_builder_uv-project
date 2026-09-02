# -*- coding: utf-8 -*-

"""
Unit tests for :mod:`aws_lbd_art_builder_uv.layer.uv_sync_options`.

Pure argument rendering — no uv, Docker, or AWS needed.
"""

import ast
import inspect

import pytest

from aws_lbd_art_builder_uv.layer import _build_in_container
from aws_lbd_art_builder_uv.layer.uv_sync_options import STRUCTURAL_ARGS
from aws_lbd_art_builder_uv.layer.uv_sync_options import STRUCTURAL_REASONS
from aws_lbd_art_builder_uv.layer.uv_sync_options import _flag_name
from aws_lbd_art_builder_uv.layer.uv_sync_options import UvSyncOptions


class TestUvSyncOptions:
    def test_default_is_minimal(self):
        # The default must stay "dependencies only, no dev group", because
        # that is what every existing caller already gets today.
        assert UvSyncOptions().to_args() == ["--frozen", "--no-dev"]

    def test_multiple_extras(self):
        opts = UvSyncOptions(extras=["aws", "web"])
        assert opts.to_args() == [
            "--frozen",
            "--no-dev",
            "--extra",
            "aws",
            "--extra",
            "web",
        ]

    def test_all_extras_with_exclusion(self):
        opts = UvSyncOptions(all_extras=True, no_extras=["dev-tools"])
        assert opts.to_args() == [
            "--frozen",
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
            "--frozen",
            "--no-dev",
            "--no-default-groups",
            "--group",
            "prod",
            "--no-group",
            "docs",
        ]

    def test_all_groups(self):
        assert UvSyncOptions(all_groups=True, no_dev=False).to_args() == [
            "--frozen",
            "--all-groups",
        ]

    def test_keep_dev(self):
        assert UvSyncOptions(no_dev=False).to_args() == ["--frozen"]

    def test_frozen_is_a_field_not_a_lock(self):
        # --frozen is safe to expose: turning it off only lets versions drift
        # from the lock, which shows up in the build log.  Contrast with
        # STRUCTURAL_ARGS, where a wrong value fails silently at runtime.
        assert UvSyncOptions(frozen=False, no_dev=False).to_args() == []

    def test_extras_and_all_extras_conflict(self):
        with pytest.raises(ValueError):
            UvSyncOptions(extras=["aws"], all_extras=True)

    def test_no_extras_without_all_extras(self):
        with pytest.raises(ValueError):
            UvSyncOptions(no_extras=["aws"])


class TestExtraArgs:
    def test_pass_through(self):
        opts = UvSyncOptions(
            extras=["aws"],
            extra_args=["--python-platform", "x86_64-manylinux_2_28"],
        )
        assert opts.to_args() == [
            "--frozen",
            "--no-dev",
            "--extra",
            "aws",
            "--python-platform",
            "x86_64-manylinux_2_28",
        ]

    @pytest.mark.parametrize(
        "bad",
        [
            ["--no-install-project"],
            # the '=value' form has to be caught too, otherwise the arg that
            # actually breaks the artifact slips through
            ["--link-mode=symlink"],
        ],
    )
    def test_reject_structural_args(self, bad):
        with pytest.raises(ValueError) as e:
            UvSyncOptions(extra_args=bad)
        msg = str(e.value)
        # a bare refusal reads as territorial; the message has to carry both
        # the reason and the one supported way around it
        assert "because" in msg
        assert "step_3_2_run_uv_sync" in msg

    @pytest.mark.parametrize(
        "bad, field",
        [
            (["--extra", "aws"], "extras"),
            (["--all-extras"], "all_extras"),
            (["--group", "prod"], "groups"),
            (["--no-dev"], "no_dev"),
            (["--frozen"], "frozen"),
        ],
    )
    def test_reject_managed_args(self, bad, field):
        with pytest.raises(ValueError) as e:
            UvSyncOptions(extra_args=bad)
        # the error has to name the field to set instead, otherwise the caller
        # is told "no" without being told where to go
        assert field in str(e.value)

    def test_values_are_not_mistaken_for_flags(self):
        # 'x86_64-manylinux_2_28' is a value, not a flag; a naive check that
        # looked at every token would have to special-case it
        UvSyncOptions(extra_args=["--python-platform", "x86_64-manylinux_2_28"])

    def test_managed_args_covers_everything_to_args_emits(self):
        # Drift guard: if a new field starts emitting a flag that is missing
        # from 'managed_args', that flag becomes silently duplicable through
        # 'extra_args'.  Two objects are needed because 'extras' and
        # 'all_extras' are mutually exclusive.
        emitted = set()
        for opts in (
            UvSyncOptions(
                extras=["a"],
                groups=["g"],
                no_groups=["h"],
                all_groups=True,
                no_default_groups=True,
                no_dev=True,
                frozen=True,
            ),
            UvSyncOptions(all_extras=True, no_extras=["b"]),
        ):
            emitted.update(a for a in opts.to_args() if a.startswith("-"))
        assert emitted == set(UvSyncOptions.managed_args)


class TestStructuralArgs:
    def test_is_what_the_builders_run(self):
        # Deliberately short: a flag belongs here only if a wrong value
        # produces an artifact that installs cleanly and fails on Lambda.
        # '--frozen' was evaluated and rejected — it is a named field instead.
        assert STRUCTURAL_ARGS == [
            "--no-install-project",
            "--link-mode=copy",
        ]

    def test_every_structural_arg_has_a_reason(self):
        # The reason is quoted in the user-facing error, so a missing one would
        # be a KeyError raised from inside the validation path.
        assert {_flag_name(a) for a in STRUCTURAL_ARGS} == set(STRUCTURAL_REASONS)

    def test_container_script_copy_is_in_sync(self):
        """
        ``_build_in_container.py`` must stay pure-stdlib, so it holds a literal
        copy of :data:`STRUCTURAL_ARGS` instead of importing it.  A copy with no
        test drifts: the local build would stay correct while the container
        build quietly produced a different artifact.  Parse the script's
        ``uv_sync_command`` literal and compare.
        """
        tree = ast.parse(inspect.getsource(_build_in_container))
        literals = [
            [
                node.value
                for node in assign.value.elts
                if isinstance(node, ast.Constant)
            ]
            for assign in ast.walk(tree)
            if isinstance(assign, ast.Assign)
            and isinstance(assign.value, ast.List)
            and any(
                isinstance(t, ast.Name) and t.id == "uv_sync_command"
                for t in assign.targets
            )
        ]
        assert len(literals) == 1, "expected exactly one 'uv_sync_command' literal"
        assert literals[0] == ["sync", *STRUCTURAL_ARGS]


if __name__ == "__main__":
    from aws_lbd_art_builder_uv.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_uv.layer.uv_sync_options",
        preview=False,
    )
