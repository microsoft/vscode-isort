# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Test for formatting over LSP.
"""

import copy
import os
from threading import Event

import pytest
from hamcrest import assert_that, is_

from .lsp_test_client import constants, defaults, session, utils

FORMATTER = utils.get_server_info_defaults()
TIMEOUT = 10  # 10 seconds


@pytest.mark.parametrize(
    "action_type",
    [
        "quickfix",
        "source.organizeImports",
        ("quickfix", "source.organizeImports"),
        None,
        "",
    ],
)
def test_code_actions(action_type):
    """Test code actions."""
    init_params = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
    init_params["initializationOptions"]["settings"][0]["check"] = True

    FORMATTED_TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.py"
    UNFORMATTED_TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.unformatted"

    contents = UNFORMATTED_TEST_FILE_PATH.read_text()
    expected = FORMATTED_TEST_FILE_PATH.read_text()

    actual_diagnostics = []

    with utils.python_file(contents, UNFORMATTED_TEST_FILE_PATH.parent) as pf:
        uri = utils.as_uri(str(pf))

        with session.LspSession() as ls_session:
            ls_session.initialize(init_params)

            done = Event()

            def _handler(params):
                nonlocal actual_diagnostics
                actual_diagnostics = params
                done.set()

            ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

            ls_session.notify_did_open(
                {
                    "textDocument": {
                        "uri": uri,
                        "languageId": "python",
                        "version": 1,
                        "text": contents,
                    }
                }
            )

            # wait for some time to receive all notifications
            done.wait(TIMEOUT)

            assert_that(
                actual_diagnostics,
                is_(
                    {
                        "uri": uri,
                        "diagnostics": [
                            {
                                "range": {
                                    "start": {"line": 0, "character": 0},
                                    "end": {"line": 1, "character": 0},
                                },
                                "message": "Imports are incorrectly sorted and/or formatted.",
                                "severity": 4,
                                "code": "E",
                                "source": "isort",
                            }
                        ],
                    }
                ),
            )

            only = None
            if action_type in ("quickfix", "source.organizeImports", ""):
                only = [action_type]
            else:
                only = action_type
            actual_code_actions = ls_session.text_document_code_action(
                {
                    "textDocument": {"uri": uri},
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 0, "character": 0},
                    },
                    "context": {
                        "diagnostics": [
                            {
                                "range": {
                                    "start": {"line": 0, "character": 0},
                                    "end": {"line": 1, "character": 0},
                                },
                                "message": "Imports are incorrectly sorted and/or formatted.",
                                "severity": 4,
                                "code": "E",
                                "source": "isort",
                            }
                        ],
                        "only": only,
                    },
                },
            )

            if action_type is None or action_type == (
                "quickfix",
                "source.organizeImports",
            ):
                assert_that(
                    actual_code_actions,
                    is_(
                        [
                            {
                                "title": "isort: Organize Imports",
                                "kind": "source.organizeImports",
                                "diagnostics": [],
                                "data": uri,
                            },
                            {
                                "title": "isort: Fix import sorting and/or formatting",
                                "kind": "quickfix",
                                "diagnostics": [
                                    {
                                        "range": {
                                            "start": {"line": 0, "character": 0},
                                            "end": {"line": 1, "character": 0},
                                        },
                                        "message": "Imports are incorrectly sorted and/or formatted.",
                                        "severity": 4,
                                        "code": "E",
                                        "source": "isort",
                                    }
                                ],
                                "data": uri,
                            },
                        ]
                    ),
                )
            elif action_type == "":
                assert_that(actual_code_actions, is_(None))
            elif action_type == "quickfix":
                assert_that(
                    actual_code_actions,
                    is_(
                        [
                            {
                                "title": "isort: Fix import sorting and/or formatting",
                                "kind": "quickfix",
                                "diagnostics": [
                                    {
                                        "range": {
                                            "start": {"line": 0, "character": 0},
                                            "end": {"line": 1, "character": 0},
                                        },
                                        "message": "Imports are incorrectly sorted and/or formatted.",
                                        "severity": 4,
                                        "code": "E",
                                        "source": "isort",
                                    }
                                ],
                                "data": uri,
                            },
                        ]
                    ),
                )
            elif action_type == "source.organizeImports":
                assert_that(
                    actual_code_actions,
                    is_(
                        [
                            {
                                "title": "isort: Organize Imports",
                                "kind": "source.organizeImports",
                                "diagnostics": [],
                                "edit": {
                                    "documentChanges": [
                                        {
                                            "textDocument": {"uri": uri, "version": 1},
                                            "edits": [
                                                {
                                                    "range": {
                                                        "start": {
                                                            "line": 0,
                                                            "character": 0,
                                                        },
                                                        "end": {
                                                            "line": 3,
                                                            "character": 0,
                                                        },
                                                    },
                                                    "newText": expected,
                                                }
                                            ],
                                        }
                                    ]
                                },
                                "data": uri,
                            }
                        ]
                    ),
                )
            else:
                assert False, "Invalid action type"


@pytest.mark.parametrize("line_ending", ["\n", "\r\n"])
def test_organize_import(line_ending):
    """Test formatting a python file."""
    init_params = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
    init_params["initializationOptions"]["settings"][0]["check"] = True

    FORMATTED_TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.py"
    UNFORMATTED_TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.unformatted"

    contents = UNFORMATTED_TEST_FILE_PATH.read_text()
    expected = FORMATTED_TEST_FILE_PATH.read_text()

    # "contents" will have universalized line ending i.e '\n'.
    # update it as needed for the test
    contents = contents.replace("\n", line_ending)
    expected = expected.replace("\n", line_ending)

    actual_diagnostics = []

    with utils.python_file(contents, UNFORMATTED_TEST_FILE_PATH.parent) as pf:
        uri = utils.as_uri(str(pf))

        with session.LspSession() as ls_session:
            ls_session.initialize(init_params)

            done = Event()

            def _handler(params):
                nonlocal actual_diagnostics
                actual_diagnostics = params
                done.set()

            ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

            ls_session.notify_did_open(
                {
                    "textDocument": {
                        "uri": uri,
                        "languageId": "python",
                        "version": 1,
                        "text": contents,
                    }
                }
            )

            # wait for some time to receive all notifications
            done.wait(TIMEOUT)

            assert_that(
                actual_diagnostics,
                is_(
                    {
                        "uri": uri,
                        "diagnostics": [
                            {
                                "range": {
                                    "start": {"line": 0, "character": 0},
                                    "end": {"line": 1, "character": 0},
                                },
                                "message": "Imports are incorrectly sorted and/or formatted.",
                                "severity": 4,
                                "code": "E",
                                "source": "isort",
                            }
                        ],
                    }
                ),
            )

            actual_code_actions = ls_session.text_document_code_action(
                {
                    "textDocument": {"uri": uri},
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 0, "character": 0},
                    },
                    "context": {
                        "diagnostics": [
                            {
                                "range": {
                                    "start": {"line": 0, "character": 0},
                                    "end": {"line": 1, "character": 0},
                                },
                                "message": "Imports are incorrectly sorted and/or formatted.",
                                "severity": 4,
                                "code": "E",
                                "source": "isort",
                            }
                        ]
                    },
                }
            )

            assert_that(
                actual_code_actions,
                is_(
                    [
                        {
                            "title": "isort: Organize Imports",
                            "kind": "source.organizeImports",
                            "diagnostics": [],
                            "data": uri,
                        },
                        {
                            "title": "isort: Fix import sorting and/or formatting",
                            "kind": "quickfix",
                            "diagnostics": [
                                {
                                    "range": {
                                        "start": {"line": 0, "character": 0},
                                        "end": {"line": 1, "character": 0},
                                    },
                                    "message": "Imports are incorrectly sorted and/or formatted.",
                                    "severity": 4,
                                    "code": "E",
                                    "source": "isort",
                                }
                            ],
                            "data": uri,
                        },
                    ]
                ),
            )

            actual_resolved_code_action = ls_session.code_action_resolve(
                actual_code_actions[0]
            )
            assert_that(
                actual_resolved_code_action,
                is_(
                    {
                        "title": "isort: Organize Imports",
                        "kind": "source.organizeImports",
                        "diagnostics": [],
                        "edit": {
                            "documentChanges": [
                                {
                                    "textDocument": {
                                        "uri": uri,
                                        "version": 1,
                                    },
                                    "edits": [
                                        {
                                            "range": {
                                                "start": {"line": 0, "character": 0},
                                                "end": {"line": 3, "character": 0},
                                            },
                                            "newText": expected,
                                        }
                                    ],
                                }
                            ]
                        },
                        "data": uri,
                    }
                ),
            )


@pytest.mark.parametrize("line_ending", ["\n", "\r\n"])
def test_organize_import_cell(line_ending):
    """Test formatting a python file."""
    init_params = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
    init_params["initializationOptions"]["settings"][0]["check"] = True

    FORMATTED_TEST_FILE_PATH = constants.TEST_DATA / "sample2" / "sample.formatted"
    UNFORMATTED_TEST_FILE_PATH = constants.TEST_DATA / "sample2" / "sample.unformatted"

    contents = UNFORMATTED_TEST_FILE_PATH.read_text()
    expected = FORMATTED_TEST_FILE_PATH.read_text()

    # "contents" will have universalized line ending i.e '\n'.
    # update it as needed for the test
    contents = contents.replace("\n", line_ending)
    expected = expected.replace("\n", line_ending)

    actual_diagnostics = []
    with utils.python_file("", UNFORMATTED_TEST_FILE_PATH.parent, ".ipynb") as pf:
        # generate a fake cell uri
        uri = utils.as_uri(pf).replace("file:", "vscode-notebook-cell:") + "#C00001"
        with session.LspSession() as ls_session:
            ls_session.initialize(init_params)

            done = Event()

            def _handler(params):
                nonlocal actual_diagnostics
                actual_diagnostics = params
                done.set()

            ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

            ls_session.notify_did_open(
                {
                    "textDocument": {
                        "uri": uri,
                        "languageId": "python",
                        "version": 1,
                        "text": contents,
                    }
                }
            )

            # wait for some time to receive all notifications
            done.wait(TIMEOUT)

            assert_that(
                actual_diagnostics,
                is_(
                    {
                        "uri": uri,
                        "diagnostics": [
                            {
                                "range": {
                                    "start": {"line": 0, "character": 0},
                                    "end": {"line": 1, "character": 0},
                                },
                                "message": "Imports are incorrectly sorted and/or formatted.",
                                "severity": 4,
                                "code": "E",
                                "source": "isort",
                            }
                        ],
                    }
                ),
            )

            actual_code_actions = ls_session.text_document_code_action(
                {
                    "textDocument": {"uri": uri},
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 0, "character": 0},
                    },
                    "context": {
                        "diagnostics": [
                            {
                                "range": {
                                    "start": {"line": 0, "character": 0},
                                    "end": {"line": 1, "character": 0},
                                },
                                "message": "Imports are incorrectly sorted and/or formatted.",
                                "severity": 4,
                                "code": "E",
                                "source": "isort",
                            }
                        ]
                    },
                }
            )

            assert_that(
                actual_code_actions,
                is_(
                    [
                        {
                            "title": "isort: Organize Imports",
                            "kind": "source.organizeImports",
                            "diagnostics": [],
                            "data": uri,
                        },
                        {
                            "title": "isort: Fix import sorting and/or formatting",
                            "kind": "quickfix",
                            "diagnostics": [
                                {
                                    "range": {
                                        "start": {"line": 0, "character": 0},
                                        "end": {"line": 1, "character": 0},
                                    },
                                    "message": "Imports are incorrectly sorted and/or formatted.",
                                    "severity": 4,
                                    "code": "E",
                                    "source": "isort",
                                }
                            ],
                            "data": uri,
                        },
                    ]
                ),
            )

            actual_resolved_code_action = ls_session.code_action_resolve(
                actual_code_actions[0]
            )
            assert_that(
                actual_resolved_code_action,
                is_(
                    {
                        "title": "isort: Organize Imports",
                        "kind": "source.organizeImports",
                        "diagnostics": [],
                        "edit": {
                            "documentChanges": [
                                {
                                    "textDocument": {
                                        "uri": uri,
                                        "version": 1,
                                    },
                                    "edits": [
                                        {
                                            "range": {
                                                "start": {"line": 0, "character": 0},
                                                "end": {"line": 4, "character": 0},
                                            },
                                            "newText": expected,
                                        }
                                    ],
                                }
                            ]
                        },
                        "data": uri,
                    }
                ),
            )


def test_check_disabled():
    """Test sort checking disabled."""
    init_params = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
    init_params["initializationOptions"]["settings"][0]["check"] = False

    UNFORMATTED_TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.unformatted"
    uri = utils.as_uri(os.fspath(UNFORMATTED_TEST_FILE_PATH))

    contents = UNFORMATTED_TEST_FILE_PATH.read_text()
    actual_diagnostics = []

    with session.LspSession() as ls_session:
        ls_session.initialize(init_params)

        done = Event()

        def _handler(params):
            nonlocal actual_diagnostics
            actual_diagnostics = params
            done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.notify_did_open(
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for some time to receive all notifications
        done.wait(TIMEOUT)

        assert_that(actual_diagnostics, is_({"uri": uri, "diagnostics": []}))


def test_organize_import_cell_with_magic_commands():
    """Test that isort handles notebook cells containing magic commands."""
    init_params = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
    init_params["initializationOptions"]["settings"][0]["check"] = True

    FORMATTED_TEST_FILE_PATH = (
        constants.TEST_DATA / "sample_magic" / "sample.formatted"
    )
    UNFORMATTED_TEST_FILE_PATH = (
        constants.TEST_DATA / "sample_magic" / "sample.unformatted"
    )

    contents = UNFORMATTED_TEST_FILE_PATH.read_text()
    expected = FORMATTED_TEST_FILE_PATH.read_text()

    actual_diagnostics = []
    with utils.python_file("", UNFORMATTED_TEST_FILE_PATH.parent, ".ipynb") as pf:
        # generate a fake cell uri
        uri = utils.as_uri(pf).replace("file:", "vscode-notebook-cell:") + "#C00001"
        with session.LspSession() as ls_session:
            ls_session.initialize(init_params)

            done = Event()

            def _handler(params):
                nonlocal actual_diagnostics
                actual_diagnostics = params
                done.set()

            ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

            ls_session.notify_did_open(
                {
                    "textDocument": {
                        "uri": uri,
                        "languageId": "python",
                        "version": 1,
                        "text": contents,
                    }
                }
            )

            # wait for some time to receive all notifications
            done.wait(TIMEOUT)

            # The server should not crash and should return diagnostics
            assert_that(actual_diagnostics["uri"], is_(uri))
            assert isinstance(actual_diagnostics["diagnostics"], list)

            actual_code_actions = ls_session.text_document_code_action(
                {
                    "textDocument": {"uri": uri},
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 0, "character": 0},
                    },
                    "context": {
                        "diagnostics": actual_diagnostics.get("diagnostics", []),
                    },
                }
            )

            # Should return code actions without crashing
            assert actual_code_actions is not None

            organize_actions = [
                a
                for a in actual_code_actions
                if a.get("kind") == "source.organizeImports"
            ]
            assert_that(len(organize_actions), is_(1))

            # Resolve the organize imports action
            actual_resolved = ls_session.code_action_resolve(organize_actions[0])

            # Verify the edit sorts imports while preserving the magic command
            edits = actual_resolved["edit"]["documentChanges"][0]["edits"]
            assert len(edits) == 1
            new_text = edits[0]["newText"]
            # The magic command should be preserved at the top
            assert new_text.startswith("%matplotlib inline")
            # Imports should be sorted (os before sys)
            assert new_text.index("import os") < new_text.index("import sys")
