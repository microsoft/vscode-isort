# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Tests that bundled package metadata is intact.

The extension ships bundled Python packages in ``bundled/libs/``.
Some packages (e.g. isort 8.x) use ``importlib.metadata`` at runtime
to resolve their version string, which requires the corresponding
``.dist-info`` directory to be present.  These tests verify the
metadata was not accidentally excluded (see issue #649).
"""

import importlib.metadata
import pathlib
import sys

import pytest

BUNDLED_LIBS = pathlib.Path(__file__).parent.parent.parent.parent / "bundled" / "libs"


@pytest.fixture(autouse=True)
def _ensure_bundled_on_path():
    """Temporarily prepend ``bundled/libs`` to ``sys.path``."""
    libs = str(BUNDLED_LIBS)
    if libs not in sys.path:
        sys.path.insert(0, libs)
        yield
        sys.path.remove(libs)
    else:
        yield


def test_isort_metadata_version():
    """importlib.metadata must be able to resolve the bundled isort version.

    This is the exact call that ``isort._version`` makes at import time.
    If the ``isort-*.dist-info`` directory is missing (e.g. stripped by
    ``.vscodeignore``), this raises ``PackageNotFoundError``.
    """
    version = importlib.metadata.version("isort")
    assert version, "isort version string should not be empty"
    # Basic sanity: version should look like a PEP 440 version
    parts = version.split(".")
    assert len(parts) >= 2, f"Unexpected version format: {version}"
