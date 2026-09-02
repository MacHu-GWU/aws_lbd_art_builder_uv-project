# -*- coding: utf-8 -*-

"""
Declarative ``uv sync`` options for Lambda layer builds.

``uv sync`` has roughly forty command line flags.  They are sorted here by one
question only: **what happens if the user gets it wrong?**

- Two of them cannot be exposed safely at all, because a wrong value produces an
  artifact that *looks* fine and fails later on Lambda.  Those are
  :data:`STRUCTURAL_ARGS`, and this class refuses them with an explanation of
  why plus the one supported way around them.
- Everything else is the user's choice and gets exposed: the common ones as
  named, validated fields, the rest verbatim through
  :attr:`UvSyncOptions.extra_args`.

So there is a single answer to "which flags does this class manage?":  all of
them.  Two by refusing them and saying why, the useful ones by name, the long
tail by pass-through -- and ``extra_args`` is cross-checked against the other
two so a flag can never be supplied twice or quietly fight the builder.

``extra_args`` doubles as the staging area for future named fields: when a flag
keeps showing up there (``--python-platform`` is the likely first), promote it.
"""

import typing as T
import dataclasses


STRUCTURAL_ARGS = [
    "--no-install-project",
    "--link-mode=copy",
]
"""
The ``uv sync`` flags a Lambda layer build cannot expose safely.

These two are not withheld because the builder "owns" them -- they are withheld
because getting either wrong yields an artifact that installs cleanly, passes
validation, and then fails at Lambda runtime.  See :data:`STRUCTURAL_REASONS`.

The container-side script (``_build_in_container.py``) keeps its own literal
copy of this list because it must stay pure-stdlib and import-free; a test
(``test_container_script_copy_is_in_sync``) guards the two against drift.
"""

STRUCTURAL_REASONS = {
    "--no-install-project": (
        "the layer carries dependencies only, and the build directory holds "
        "just pyproject.toml + uv.lock -- with no source tree there, uv "
        "installs the project as an *editable* pointer into the build "
        "directory, which yields an unimportable package and a .pth file "
        "referencing a host path that does not exist on Lambda"
    ),
    "--link-mode": (
        "layers are zipped and uploaded, and symlink targets do not exist in "
        "the Lambda execution environment"
    ),
}
"""
Why each :data:`STRUCTURAL_ARGS` entry is not configurable, keyed by flag name.

Quoted verbatim in the error the user sees.  A refusal without a reason reads
as the library being territorial; with one, it reads as a warning.
"""


def _flag_name(arg: str) -> str:
    """
    Reduce a command line token to its bare flag name.

    ``--link-mode=copy`` -> ``--link-mode``, ``--extra`` -> ``--extra``, and a
    bare value such as ``copy`` -> ``""`` (it is a value, not a flag).
    """
    if not arg.startswith("-"):
        return ""
    return arg.split("=", 1)[0]


@dataclasses.dataclass(frozen=True)
class UvSyncOptions:
    """
    Which dependencies to install into the layer, and any extra ``uv sync`` flags.

    See https://docs.astral.sh/uv/reference/cli/#uv-sync for the authoritative
    semantics of each underlying flag.

    :param extras: Extra names from ``[project.optional-dependencies]`` to
        include.  Emits one ``--extra`` flag per name, so multiple extras are
        supported.  Mutually exclusive with ``all_extras``.
    :param all_extras: Include every declared extra (``--all-extras``).
    :param no_extras: Extras to exclude, only meaningful together with
        ``all_extras`` (``--no-extra``).
    :param groups: Dependency groups from ``[dependency-groups]`` to include
        (``--group``).
    :param no_groups: Dependency groups to exclude (``--no-group``).
    :param all_groups: Include every declared dependency group (``--all-groups``).
    :param no_default_groups: Ignore ``[tool.uv] default-groups``
        (``--no-default-groups``).
    :param no_dev: Exclude the ``dev`` dependency group (``--no-dev``).  Defaults
        to ``True`` because test / doc tooling has no place in a Lambda layer.
    :param frozen: Install the exact versions pinned in ``uv.lock`` without
        re-resolving (``--frozen``).  Defaults to ``True`` so a layer built
        today matches one built next month.  Setting it to ``False`` lets uv
        re-resolve against the index -- a legitimate choice, and a safe one to
        expose: the worst case is a layer whose versions drift from the lock,
        which is visible in the build log rather than silent at runtime.
    :param extra_args: Escape hatch for any ``uv sync`` flag this class does not
        model, e.g. ``["--python-platform", "x86_64-manylinux_2_28"]``.  Passed
        through verbatim.  Rejected at construction time if it collides with
        :data:`STRUCTURAL_ARGS` or with a flag one of the fields above already
        emits, so there is never a question of which one wins.  A rejection
        always says why and what to do instead.

    Example::

        UvSyncOptions(extras=["aws", "web"])
        # -> ["--no-dev", "--extra", "aws", "--extra", "web"]
    """

    # fmt: off
    extras: list[str] = dataclasses.field(default_factory=list)
    all_extras: bool = dataclasses.field(default=False)
    no_extras: list[str] = dataclasses.field(default_factory=list)
    groups: list[str] = dataclasses.field(default_factory=list)
    no_groups: list[str] = dataclasses.field(default_factory=list)
    all_groups: bool = dataclasses.field(default=False)
    no_default_groups: bool = dataclasses.field(default=False)
    no_dev: bool = dataclasses.field(default=True)
    frozen: bool = dataclasses.field(default=True)
    extra_args: list[str] = dataclasses.field(default_factory=list)
    # fmt: on

    #: Every flag the named fields above can emit, mapped to the field that
    #: owns it.  Used to give ``extra_args`` a precise error message, and kept
    #: as data so the check cannot drift from :meth:`to_args`.
    managed_args: T.ClassVar[dict[str, str]] = {
        "--extra": "extras",
        "--all-extras": "all_extras",
        "--no-extra": "no_extras",
        "--group": "groups",
        "--no-group": "no_groups",
        "--all-groups": "all_groups",
        "--no-default-groups": "no_default_groups",
        "--no-dev": "no_dev",
        "--frozen": "frozen",
    }

    def __post_init__(self):
        # uv itself rejects '--all-extras --extra name' at the CLI parsing
        # layer.  Failing here instead gives the caller a Python traceback at
        # construction time rather than a cryptic clap usage error minutes
        # later, after the Docker image has already been pulled.
        if self.all_extras and self.extras:
            raise ValueError(
                "'extras' and 'all_extras' are mutually exclusive; "
                "use one or the other."
            )
        # uv silently ignores '--no-extra' unless '--all-extras' is supplied,
        # which reads like the exclusion worked when it did nothing at all.
        if self.no_extras and not self.all_extras:
            raise ValueError(
                "'no_extras' only takes effect together with 'all_extras=True'."
            )
        self._check_extra_args()

    def _check_extra_args(self):
        """
        Reject ``extra_args`` entries that belong to another tier.

        Without this check the two failure modes are both silent: a structural
        flag would be passed to uv twice (uv takes the last one, so the build
        quietly stops being a layer build), and a managed flag would duplicate
        whatever the named field emitted.  Neither shows up until someone
        inspects the artifact, so both are worth an immediate ValueError.
        """
        structural = {_flag_name(arg) for arg in STRUCTURAL_ARGS}
        for arg in self.extra_args:
            flag = _flag_name(arg)
            if not flag:  # a value belonging to the preceding flag
                continue
            if flag in structural:
                raise ValueError(
                    f"'{flag}' cannot be set through 'extra_args', because "
                    f"{STRUCTURAL_REASONS[flag]}. The builder always runs: "
                    f"uv sync {' '.join(STRUCTURAL_ARGS)}. If you need a build "
                    f"that really does differ here, subclass the builder and "
                    f"override 'step_3_2_run_uv_sync' -- that path is supported, "
                    f"but arranging a working artifact is then yours to do."
                )
            if flag in self.managed_args:
                raise ValueError(
                    f"'{flag}' is already managed by this class; "
                    f"set the '{self.managed_args[flag]}' field instead of "
                    f"passing it through 'extra_args'."
                )

    def to_args(self) -> list[str]:
        """
        Render these options as ``uv sync`` command line arguments.

        Does **not** include :data:`STRUCTURAL_ARGS` -- the builders add those.
        Keeping them out is what lets this list be forwarded verbatim into the
        Docker container, where the container-side script supplies its own.

        :return: A flat argument list, ready to be spliced into the ``uv sync``
            command or forwarded to the container-side build script.
        """
        args: list[str] = []
        if self.frozen:
            args.append("--frozen")
        if self.no_dev:
            args.append("--no-dev")
        if self.no_default_groups:
            args.append("--no-default-groups")
        if self.all_extras:
            args.append("--all-extras")
        for extra in self.extras:
            args.extend(["--extra", extra])
        for extra in self.no_extras:
            args.extend(["--no-extra", extra])
        if self.all_groups:
            args.append("--all-groups")
        for group in self.groups:
            args.extend(["--group", group])
        for group in self.no_groups:
            args.extend(["--no-group", group])
        args.extend(self.extra_args)
        return args
