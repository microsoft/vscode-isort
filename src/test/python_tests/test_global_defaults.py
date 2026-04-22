# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unit tests for _get_global_defaults() in lsp_server.

Verifies that _get_global_defaults() correctly reads values from
GLOBAL_SETTINGS and falls back to expected defaults.

Mock setup is provided by conftest.py (setup_lsp_mocks).
"""

import lsp_server
import pytest


def _with_global_settings(overrides, fn):
    """Run fn with GLOBAL_SETTINGS temporarily set to overrides."""
    original = lsp_server.GLOBAL_SETTINGS.copy()
    try:
        lsp_server.GLOBAL_SETTINGS.clear()
        lsp_server.GLOBAL_SETTINGS.update(overrides)
        return fn()
    finally:
        lsp_server.GLOBAL_SETTINGS.clear()
        lsp_server.GLOBAL_SETTINGS.update(original)


@pytest.mark.parametrize(
    "overrides, key, expected",
    [
        pytest.param({"check": True}, "check", True, id="check-set"),
        pytest.param({}, "check", False, id="check-default"),
        pytest.param(
            {"path": ["/usr/bin/isort"]}, "path", ["/usr/bin/isort"], id="path-set"
        ),
        pytest.param({}, "path", [], id="path-default"),
        pytest.param(
            {"showNotifications": "always"},
            "showNotifications",
            "always",
            id="showNotifications-set",
        ),
        pytest.param(
            {"importStrategy": "fromEnvironment"},
            "importStrategy",
            "fromEnvironment",
            id="importStrategy-set",
        ),
        pytest.param(
            {"args": ["--profile", "black"]},
            "args",
            ["--profile", "black"],
            id="args-set",
        ),
        pytest.param({}, "args", [], id="args-default"),
        pytest.param(
            {"extraPaths": ["/custom/lib"]},
            "extraPaths",
            ["/custom/lib"],
            id="extraPaths-set",
        ),
        pytest.param({}, "extraPaths", [], id="extraPaths-default"),
    ],
)
def test_global_defaults_setting(overrides, key, expected):
    """Each global setting is correctly read or defaults when absent."""
    result = _with_global_settings(overrides, lsp_server._get_global_defaults)
    assert result[key] == expected
