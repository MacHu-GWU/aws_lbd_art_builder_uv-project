.. _release_history:

Release and Version History
==============================================================================


x.y.z (Backlog)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

**Minor Improvements**

**Bugfixes**

**Miscellaneous**


1.0.0 (2026-10-15)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Breaking Changes**

- Now requires ``aws_lbd_art_builder_core>=1.0.0,<2.0.0`` (was ``>=0.1.5,<1.0.0``).
  The ``upload`` and ``publish`` extras therefore pull in ``s3pathlib`` 3.x, and
  every ``s3_client`` argument of core (``upload_layer_zip_to_s3()``,
  ``LambdaLayerVersionPublisher``, ``LayerDeploymentWorkflow``, ...) only accepts
  a boto3 S3 client: pass ``bsm.s3_client`` instead of a ``BotoSesManager``.
  Import ``S3Path`` from ``s3pathlib.api``.
- ``boto_session_manager`` and ``pathlib_mate`` are no longer installed with the
  ``upload`` and ``publish`` extras. Add them to your own dependencies if you
  import them.

**Miscellaneous**

- The deployment end-to-end test and the example projects now use plain boto3
  clients and s3pathlib 3.x.


0.1.2 (2026-09-02)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- Added :class:`~aws_lbd_art_builder_uv.layer.uv_sync_options.UvSyncOptions` — a
  declarative way to choose what goes into the Lambda layer: extras from
  ``[project.optional-dependencies]``, dependency groups from
  ``[dependency-groups]``, and whether to sync from the lock file. Multiple
  extras are supported. Both
  :class:`~aws_lbd_art_builder_uv.layer.local_builder.UvLambdaLayerLocalBuilder`
  and
  :class:`~aws_lbd_art_builder_uv.layer.container_builder.UvLambdaLayerContainerBuilder`
  accept it through the new ``uv_sync_options`` field. The default reproduces
  the previous behavior exactly (project dependencies only, no dev group), so
  existing code needs no change.
- Added ``UvSyncOptions.extra_args``, which forwards any other ``uv sync`` flag
  verbatim, so a flag this library does not model is never a dead end. One
  notable use is ``--python-platform``, which pulls Linux wheels on a macOS
  host and can avoid a container build for packages with C extensions.
- ``extra_args`` entries are validated when the object is constructed, instead
  of failing minutes into a build. The error says why a flag is refused and
  names the supported alternative — the field to set instead, or overriding
  ``step_3_2_run_uv_sync``. Only ``--no-install-project`` and ``--link-mode``
  are refused outright, because a wrong value there yields a layer that
  installs cleanly, passes validation, and then fails at Lambda runtime.
- ``validate_artifacts()`` accepts ``extras`` and ``all_extras``, so packages
  pulled in by an extra are validated instead of silently skipped.

**Minor Improvements**

- The build log now prints the exact ``uv sync`` command being executed, on the
  host and inside the container alike.

**Miscellaneous**

- Requires ``aws-lbd-art-builder-core>=0.1.5`` for
  ``BaseLambdaLayerContainerBuilder.script_args``, the hook used to pass build
  options into the container.


0.1.1 (2026-04-27)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- First release
