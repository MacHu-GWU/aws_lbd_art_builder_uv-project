# -*- coding: utf-8 -*-

"""
Shared fixtures for layer tests.

The ``examples/my_lbd_app-project`` fixture project needs a ``.venv`` at its
root so that ``LayerPathLayout.venv_python_version`` can detect the Python
version (it runs ``{project_root}/.venv/bin/python --version``).

Locally this ``.venv`` already exists from ``mise run inst``, but in CI it
must be created before the e2e tests run.
"""

import subprocess
from pathlib import Path

import pytest

dir_examples = Path(__file__).parent.parent.parent / "examples"
dir_my_lbd_app = dir_examples / "my_lbd_app-project"


@pytest.fixture(autouse=True, scope="session")
def ensure_example_venv():
    """
    Create ``.venv`` in the example project if it doesn't exist.

    This is a workaround for a core bug where ``venv_python_version``
    looks at the project root's ``.venv`` instead of the build dir's.
    """
    venv_dir = dir_my_lbd_app / ".venv"
    if not (venv_dir / "bin" / "python").exists():
        subprocess.run(
            ["uv", "venv", "--allow-existing"],
            cwd=dir_my_lbd_app,
            check=True,
        )
