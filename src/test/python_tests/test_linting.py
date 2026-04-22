# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Test for linting over LSP.
"""

import copy
from threading import Event

import pytest
from hamcrest import assert_that, greater_than, is_

from .lsp_test_client import constants, defaults, session, utils

TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.unformatted"
TEST_FILE_URI = utils.as_uri(str(TEST_FILE_PATH))
LINTER = utils.get_server_info_defaults()
TIMEOUT = 10  # 10 seconds

# isort produces a single diagnostic with code "E" when imports are unsorted.
# Default severity is "Hint" (4).  The diagnostic range spans the first import line.
UNSORTED_DIAGNOSTIC = {
    "range": {
        "start": {"line": 0, "character": 0},
        "end": {"line": 1, "character": 0},
    },
    "message": "Imports are incorrectly sorted and/or formatted.",
    "severity": 4,
    "code": "E",
    "source": LINTER["name"],
}


def _get_init_params(**overrides):
    """Return init params with ``check`` enabled and optional overrides."""
    init_params = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
    settings = init_params["initializationOptions"]["settings"][0]
    settings["check"] = True
    for key, value in overrides.items():
        settings[key] = value
    return init_params


def test_publish_diagnostics_on_open():
    """Test to ensure linting on file open."""
    contents = TEST_FILE_PATH.read_text()

    actual = []
    with session.LspSession() as ls_session:
        ls_session.initialize(_get_init_params())

        done = Event()

        def _handler(params):
            nonlocal actual
            actual = params
            done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.notify_did_open(
            {
                "textDocument": {
                    "uri": TEST_FILE_URI,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for some time to receive all notifications
        done.wait(TIMEOUT)

    expected = {
        "uri": TEST_FILE_URI,
        "diagnostics": [UNSORTED_DIAGNOSTIC],
    }

    assert_that(actual, is_(expected))


def test_publish_diagnostics_on_save():
    """Test to ensure linting on file save."""
    contents = TEST_FILE_PATH.read_text()

    actual = []
    with session.LspSession() as ls_session:
        ls_session.initialize(_get_init_params())

        done = Event()

        def _handler(params):
            nonlocal actual
            actual = params
            done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.notify_did_save(
            {
                "textDocument": {
                    "uri": TEST_FILE_URI,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for some time to receive all notifications
        done.wait(TIMEOUT)

    expected = {
        "uri": TEST_FILE_URI,
        "diagnostics": [UNSORTED_DIAGNOSTIC],
    }

    assert_that(actual, is_(expected))


def test_publish_diagnostics_on_close():
    """Test to ensure diagnostic clean-up on file close."""
    contents = TEST_FILE_PATH.read_text()

    actual = []
    with session.LspSession() as ls_session:
        ls_session.initialize(_get_init_params())

        done = Event()

        def _handler(params):
            nonlocal actual
            actual = params
            done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.notify_did_open(
            {
                "textDocument": {
                    "uri": TEST_FILE_URI,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for some time to receive all notifications
        done.wait(TIMEOUT)

        # We should receive some diagnostics
        assert_that(len(actual), is_(greater_than(0)))

        # reset waiting
        done.clear()

        ls_session.notify_did_close(
            {
                "textDocument": {
                    "uri": TEST_FILE_URI,
                    "languageId": "python",
                    "version": 1,
                }
            }
        )

        # wait for some time to receive all notifications
        done.wait(TIMEOUT)

    # On close should clear out everything
    expected = {
        "uri": TEST_FILE_URI,
        "diagnostics": [],
    }
    assert_that(actual, is_(expected))


@pytest.mark.parametrize(
    "severity_value, expected_severity",
    [
        ("Error", 1),
        ("Warning", 2),
        ("Information", 3),
        ("Hint", 4),
    ],
)
def test_severity_setting(severity_value, expected_severity):
    """Test to ensure severity setting is honored."""
    contents = TEST_FILE_PATH.read_text()

    actual = []
    with session.LspSession() as ls_session:
        ls_session.initialize(
            _get_init_params(severity={"E": severity_value, "W": "Warning"})
        )

        done = Event()

        def _handler(params):
            nonlocal actual
            actual = params
            done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.notify_did_open(
            {
                "textDocument": {
                    "uri": TEST_FILE_URI,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for some time to receive all notifications
        done.wait(TIMEOUT)

    expected = {
        "uri": TEST_FILE_URI,
        "diagnostics": [
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 1, "character": 0},
                },
                "message": "Imports are incorrectly sorted and/or formatted.",
                "severity": expected_severity,
                "code": "E",
                "source": LINTER["name"],
            },
        ],
    }

    assert_that(actual, is_(expected))


@pytest.mark.parametrize("check", [True, False])
def test_check_setting(check):
    """Test to ensure the check (enabled) setting is honored."""
    contents = TEST_FILE_PATH.read_text()

    actual = []
    with session.LspSession() as ls_session:
        ls_session.initialize(_get_init_params(check=check))

        done = Event()

        def _handler(params):
            nonlocal actual
            actual = params
            done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.notify_did_open(
            {
                "textDocument": {
                    "uri": TEST_FILE_URI,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for some time to receive all notifications
        done.wait(TIMEOUT)

    if check:
        expected = {
            "uri": TEST_FILE_URI,
            "diagnostics": [UNSORTED_DIAGNOSTIC],
        }
    else:
        expected = {
            "uri": TEST_FILE_URI,
            "diagnostics": [],
        }

    assert_that(actual, is_(expected))
