# -*- coding: utf-8 -*-

"""
Declarative dependency-selection options for ``uv sync``.

By default a Lambda layer build installs exactly the ``[project] dependencies``
table -- no extras, no dependency groups.  That is the right default (a layer
should be as small as possible), but it is not always what the user wants: a
project may declare ``[project.optional-dependencies]`` and expect the layer to
carry one or more of them.

:class:`UvSyncOptions` turns that choice into data.  The builders own the
"structural" flags that are never negotiable (``--frozen``,
``--no-install-project``, ``--link-mode=copy``); this class owns only the flags
that decide *which* dependencies get installed.  Keeping the two sets apart is
what lets the same option object travel from the host into the Docker container
(as plain command line arguments) without dragging build mechanics along with it.
"""

import dataclasses


@dataclasses.dataclass(frozen=True)
class UvSyncOptions:
    """
    Which optional dependencies to include in the layer.

    Mirrors the dependency-selection flags of ``uv sync``.  See
    https://docs.astral.sh/uv/reference/cli/#uv-sync for the authoritative
    semantics of each flag.

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
    # fmt: on

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

    def to_args(self) -> list[str]:
        """
        Render these options as ``uv sync`` command line arguments.

        :return: A flat argument list, ready to be spliced into the ``uv sync``
            command or forwarded to the container-side build script.
        """
        args: list[str] = []
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
        return args
