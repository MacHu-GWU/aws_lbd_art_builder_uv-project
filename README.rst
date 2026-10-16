
.. image:: https://readthedocs.org/projects/aws-lbd-art-builder-uv/badge/?version=latest
    :target: https://aws-lbd-art-builder-uv.readthedocs.io/en/latest/
    :alt: Documentation Status

.. image:: https://github.com/MacHu-GWU/aws_lbd_art_builder_uv-project/actions/workflows/main.yml/badge.svg
    :target: https://github.com/MacHu-GWU/aws_lbd_art_builder_uv-project/actions?query=workflow:CI

.. image:: https://codecov.io/gh/MacHu-GWU/aws_lbd_art_builder_uv-project/branch/main/graph/badge.svg
    :target: https://codecov.io/gh/MacHu-GWU/aws_lbd_art_builder_uv-project

.. image:: https://img.shields.io/pypi/v/aws-lbd-art-builder-uv.svg
    :target: https://pypi.python.org/pypi/aws-lbd-art-builder-uv

.. image:: https://img.shields.io/pypi/l/aws-lbd-art-builder-uv.svg
    :target: https://pypi.python.org/pypi/aws-lbd-art-builder-uv

.. image:: https://img.shields.io/pypi/pyversions/aws-lbd-art-builder-uv.svg
    :target: https://pypi.python.org/pypi/aws-lbd-art-builder-uv

.. image:: https://img.shields.io/badge/✍️_Release_History!--None.svg?style=social&logo=github
    :target: https://github.com/MacHu-GWU/aws_lbd_art_builder_uv-project/blob/main/release-history.rst

.. image:: https://img.shields.io/badge/⭐_Star_me_on_GitHub!--None.svg?style=social&logo=github
    :target: https://github.com/MacHu-GWU/aws_lbd_art_builder_uv-project

------

.. image:: https://img.shields.io/badge/Link-API-blue.svg
    :target: https://aws-lbd-art-builder-uv.readthedocs.io/en/latest/py-modindex.html

.. image:: https://img.shields.io/badge/Link-Install-blue.svg
    :target: `install`_

.. image:: https://img.shields.io/badge/Link-GitHub-blue.svg
    :target: https://github.com/MacHu-GWU/aws_lbd_art_builder_uv-project

.. image:: https://img.shields.io/badge/Link-Submit_Issue-blue.svg
    :target: https://github.com/MacHu-GWU/aws_lbd_art_builder_uv-project/issues

.. image:: https://img.shields.io/badge/Link-Request_Feature-blue.svg
    :target: https://github.com/MacHu-GWU/aws_lbd_art_builder_uv-project/issues

.. image:: https://img.shields.io/badge/Link-Download-blue.svg
    :target: https://pypi.org/pypi/aws-lbd-art-builder-uv#files


Welcome to ``aws_lbd_art_builder_uv`` Documentation
==============================================================================
.. image:: https://aws-lbd-art-builder-uv.readthedocs.io/en/latest/_static/aws_lbd_art_builder_uv-logo.png
    :target: https://aws-lbd-art-builder-uv.readthedocs.io/en/latest/

``aws_lbd_art_builder_uv`` is the **uv** builder for `aws_lbd_art_builder_core <https://github.com/MacHu-GWU/aws_lbd_art_builder_core-project>`_: it turns a project's ``pyproject.toml`` and ``uv.lock`` into the ``python/`` folder of an AWS Lambda layer, using `uv <https://docs.astral.sh/uv/>`_.

It offers two builders:

- **UvLambdaLayerLocalBuilder**: runs ``uv sync`` on the host. Fast, no Docker. Best for pure-Python dependencies.
- **UvLambdaLayerContainerBuilder**: runs ``uv sync`` inside an `AWS SAM build image <https://gallery.ecr.aws/sam>`_, so packages with C extensions (``numpy``, ``pydantic-core``, ...) get Linux binaries for the target Python and architecture.

Both run four steps (Preflight Check → Prepare Environment → Execute Build → Finalize Artifacts) and leave the layer content in ``build/lambda/layer/artifacts/python/``. Zipping, uploading, and publishing the layer come from ``aws_lbd_art_builder_core``, re-exported here.

Features:

- Reproducible builds: ``uv sync --frozen`` from the lock file, project itself never installed.
- ``UvSyncOptions`` picks what goes into the layer: extras, dependency groups, and any other ``uv sync`` flag, checked when the object is built.
- Private package indexes (e.g. AWS CodeArtifact) through ``Credentials``.
- ``validate_artifacts`` checks that every dependency landed in the layer, and optionally that its wheels target Linux.

.. tip::

    This repo ships two Claude Code agent skills in ``.claude/skills/``:

    - ``pypi-aws_lbd_art_builder_uv``: the public API, for coding agents that **use** this library. Copy the folder into the ``.claude/skills/`` of the project that depends on it (together with ``pypi-aws_lbd_art_builder_core`` if that project also calls core directly).
    - ``maintain-aws_lbd_art_builder_uv``: how the builders, the container build, and the tests work inside, for coding agents that **change** this repo. It is available automatically when you work in this repo.


Quick Look
------------------------------------------------------------------------------
Build a layer in a container, check it, then zip, upload, and publish it:

.. code-block:: python

    from pathlib import Path

    import boto3
    from s3pathlib.api import S3Path
    import aws_lbd_art_builder_uv.api as aws_lbd_art_builder_uv

    layer_api = aws_lbd_art_builder_uv.layer_api
    path_pyproject_toml = Path("/path/to/my_app-project/pyproject.toml")

    builder = layer_api.UvLambdaLayerContainerBuilder(
        path_pyproject_toml=path_pyproject_toml,
        py_ver_major=3,
        py_ver_minor=12,
        is_arm=False,
        skip_prompt=True,
        uv_sync_options=layer_api.UvSyncOptions(extras=["aws"]),
    )
    builder.run()
    layer_api.validate_artifacts(
        dir_python=builder.path_layout.dir_python,
        path_pyproject_toml=path_pyproject_toml,
        check_linux=True,
        extras=["aws"],
    )

    boto_ses = boto3.Session()
    s3dir_lambda = S3Path("s3://my-bucket/projects/my_app/lambda/")
    layer_api.create_layer_zip_file(
        dir_python=builder.path_layout.dir_python,
        path_layer_zip=builder.path_layout.path_build_lambda_layer_zip,
    )
    layer_api.upload_layer_zip_to_s3(
        s3_client=boto_ses.client("s3"),
        path_pyproject_toml=path_pyproject_toml,
        s3dir_lambda=s3dir_lambda,
        path_manifest=path_pyproject_toml.parent / "uv.lock",
    )
    deployment = layer_api.LambdaLayerVersionPublisher(
        path_pyproject_toml=path_pyproject_toml,
        s3dir_lambda=s3dir_lambda,
        path_manifest=path_pyproject_toml.parent / "uv.lock",
        s3_client=boto_ses.client("s3"),
        layer_name="my_app",
        lambda_client=boto_ses.client("lambda"),
    ).run()  # raises ValueError if uv.lock is unchanged since the last version
    print(deployment.layer_version_arn)

Pass plain boto3 clients. S3 locations are ``s3pathlib`` 3.x ``S3Path`` objects. The project needs a ``.venv`` with the same Python minor version as the build (``uv venv --python 3.12``). Core's ``LayerDeploymentWorkflow`` runs the same steps in one call with either builder.


.. _install:

Install
------------------------------------------------------------------------------

``aws_lbd_art_builder_uv`` is released on PyPI and supports Python 3.11 to 3.14. It needs ``uv`` on ``PATH``, and Docker for container builds. The base install builds and validates layers; uploading and publishing need an extra:

.. code-block:: console

    $ pip install aws-lbd-art-builder-uv                  # build and validate
    $ pip install "aws-lbd-art-builder-uv[upload]"        # + S3 upload (boto3, s3pathlib 3.x)
    $ pip install "aws-lbd-art-builder-uv[publish]"       # + publish Lambda layer versions

To upgrade to latest version:

.. code-block:: console

    $ pip install --upgrade "aws-lbd-art-builder-uv[publish]"

Upgrading from 0.x: 1.0.0 requires ``aws_lbd_art_builder_core`` 1.x, which moved to ``s3pathlib`` 3.x and no longer accepts a ``BotoSesManager`` as ``s3_client``; see the `release history <https://github.com/MacHu-GWU/aws_lbd_art_builder_uv-project/blob/main/release-history.rst>`_.
