# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unit tests for _get_global_defaults() in lsp_server.

Verifies that _get_global_defaults() correctly reads values from
GLOBAL_SETTINGS and falls back to expected defaults.

Mock setup is provided by conftest.py (setup_lsp_mocks).
"""

import lsp_server


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


def test_check_read_from_global_settings():
    """_get_global_defaults() returns check from GLOBAL_SETTINGS."""
    result = _with_global_settings(
        {"check": True},
        lsp_server._get_global_defaults,
    )
    assert result["check"] is True


def test_check_defaults_to_false():
    """_get_global_defaults() returns False when GLOBAL_SETTINGS has no check."""
    result = _with_global_settings({}, lsp_server._get_global_defaults)
    assert result["check"] is False


def test_path_read_from_global_settings():
    """_get_global_defaults() returns path from GLOBAL_SETTINGS."""
    result = _with_global_settings(
        {"path": ["/usr/bin/isort"]},
        lsp_server._get_global_defaults,
    )
    assert result["path"] == ["/usr/bin/isort"]


def test_path_defaults_to_empty_list():
    """_get_global_defaults() returns [] when GLOBAL_SETTINGS has no path."""
    result = _with_global_settings({}, lsp_server._get_global_defaults)
    assert result["path"] == []


def test_show_notifications_read_from_global_settings():
    """_get_global_defaults() returns showNotifications from GLOBAL_SETTINGS."""
    result = _with_global_settings(
        {"showNotifications": "always"},
        lsp_server._get_global_defaults,
    )
    assert result["showNotifications"] == "always"


def test_import_strategy_read_from_global_settings():
    """_get_global_defaults() returns importStrategy from GLOBAL_SETTINGS."""
    result = _with_global_settings(
        {"importStrategy": "fromEnvironment"},
        lsp_server._get_global_defaults,
    )
    assert result["importStrategy"] == "fromEnvironment"


def test_args_read_from_global_settings():
    """_get_global_defaults() returns args from GLOBAL_SETTINGS."""
    result = _with_global_settings(
        {"args": ["--profile", "black"]},
        lsp_server._get_global_defaults,
    )
    assert result["args"] == ["--profile", "black"]


def test_args_defaults_to_empty_list():
    """_get_global_defaults() returns [] when GLOBAL_SETTINGS has no args."""
    result = _with_global_settings({}, lsp_server._get_global_defaults)
    assert result["args"] == []


def test_extra_paths_read_from_global_settings():
    """_get_global_defaults() returns extraPaths from GLOBAL_SETTINGS."""
    result = _with_global_settings(
        {"extraPaths": ["/custom/lib"]},
        lsp_server._get_global_defaults,
    )
    assert result["extraPaths"] == ["/custom/lib"]


def test_extra_paths_defaults_to_empty_list():
    """_get_global_defaults() returns [] when GLOBAL_SETTINGS has no extraPaths."""
    result = _with_global_settings({}, lsp_server._get_global_defaults)
    assert result["extraPaths"] == []
