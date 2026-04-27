
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

``aws_lbd_art_builder_uv`` is the **uv** backend for `aws_lbd_art_builder_core <https://github.com/MacHu-GWU/aws_lbd_art_builder_core-project>`_, providing automated AWS Lambda layer builds using `uv <https://docs.astral.sh/uv/>`_ as the package manager.

It offers two builders:

- **UvLambdaLayerLocalBuilder** — runs ``uv sync`` directly on the host machine. Fast, no Docker required. Best for pure-Python dependencies.
- **UvLambdaLayerContainerBuilder** — runs ``uv sync`` inside an `AWS SAM Docker image <https://gallery.ecr.aws/sam>`_ to produce Linux-compatible binaries. Required when your layer includes packages with C extensions (e.g. ``numpy``, ``pandas``).

Both builders follow a 4-step workflow: **Preflight Check → Prepare Environment → Execute Build → Finalize Artifacts**. The output is a ``artifacts/python/`` directory ready to be zipped and published as a Lambda layer. Combine with ``aws_lbd_art_builder_core``'s package, upload, and publish steps for a complete deployment pipeline.

Features:

- Reproducible builds via ``uv sync --frozen`` with lock files
- Private PyPI index support (e.g. AWS CodeArtifact) via credential injection
- Artifact validation — verify installed packages match ``pyproject.toml`` dependencies
- Pure-stdlib container script — no pip install needed inside the container


.. _install:

Install
------------------------------------------------------------------------------

``aws_lbd_art_builder_uv`` is released on PyPI, so all you need is to:

.. code-block:: console

    $ pip install aws-lbd-art-builder-uv

To upgrade to latest version:

.. code-block:: console

    $ pip install --upgrade aws-lbd-art-builder-uv
