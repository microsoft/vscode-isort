# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Tests for notebook document LSP handlers.
"""

import copy
from threading import Event

from hamcrest import assert_that, is_

from .lsp_test_client import constants, defaults, session, utils

TIMEOUT = 10  # 10 seconds


def _make_cell_uri(notebook_path, cell_id="C00001"):
    """Build a fake notebook cell URI from a file path."""
    return (
        utils.as_uri(notebook_path).replace("file:", "vscode-notebook-cell:")
        + f"#{cell_id}"
    )


def _make_notebook_uri(notebook_path):
    """Build a notebook URI from a file path."""
    return utils.as_uri(notebook_path)


def _collect_diagnostics(ls_session, count=1, timeout=TIMEOUT):
    """Collect a number of publishDiagnostics notifications."""
    results = []
    done = Event()

    def _handler(params):
        results.append(params)
        if len(results) >= count:
            done.set()

    ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)
    return results, done


def test_notebook_did_open():
    """Opening a notebook should publish diagnostics for each cell."""
    init_params = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
    init_params["initializationOptions"]["settings"][0]["check"] = True

    UNFORMATTED = constants.TEST_DATA / "sample2" / "sample.unformatted"
    contents = UNFORMATTED.read_text()

    with utils.python_file("", UNFORMATTED.parent, ".ipynb") as pf:
        notebook_uri = _make_notebook_uri(pf)
        cell_uri = _make_cell_uri(pf, "C00001")

        with session.LspSession() as ls_session:
            ls_session.initialize(init_params)
            results, done = _collect_diagnostics(ls_session, count=1)

            ls_session.notify_notebook_did_open(
                {
                    "notebookDocument": {
                        "uri": notebook_uri,
                        "notebookType": "jupyter-notebook",
                        "version": 0,
                        "cells": [
                            {
                                "kind": 2,  # Code
                                "document": cell_uri,
                            },
                        ],
                    },
                    "cellTextDocuments": [
                        {
                            "uri": cell_uri,
                            "languageId": "python",
                            "version": 1,
                            "text": contents,
                        },
                    ],
                }
            )

            done.wait(TIMEOUT)

            assert len(results) >= 1
            cell_diag = next(r for r in results if r["uri"] == cell_uri)
            assert_that(len(cell_diag["diagnostics"]), is_(1))
            assert_that(cell_diag["diagnostics"][0]["code"], is_("E"))
            assert_that(cell_diag["diagnostics"][0]["source"], is_("isort"))


def test_notebook_did_change_text_content():
    """Editing a cell's text should re-lint only that cell."""
    init_params = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
    init_params["initializationOptions"]["settings"][0]["check"] = True

    UNFORMATTED = constants.TEST_DATA / "sample2" / "sample.unformatted"
    FORMATTED = constants.TEST_DATA / "sample2" / "sample.formatted"
    unsorted_contents = UNFORMATTED.read_text()
    sorted_contents = FORMATTED.read_text()

    with utils.python_file("", UNFORMATTED.parent, ".ipynb") as pf:
        notebook_uri = _make_notebook_uri(pf)
        cell_uri = _make_cell_uri(pf, "C00001")

        with session.LspSession() as ls_session:
            ls_session.initialize(init_params)

            # Open with unsorted imports — expect diagnostics.
            open_results, open_done = _collect_diagnostics(ls_session, count=1)
            ls_session.notify_notebook_did_open(
                {
                    "notebookDocument": {
                        "uri": notebook_uri,
                        "notebookType": "jupyter-notebook",
                        "version": 0,
                        "cells": [
                            {"kind": 2, "document": cell_uri},
                        ],
                    },
                    "cellTextDocuments": [
                        {
                            "uri": cell_uri,
                            "languageId": "python",
                            "version": 1,
                            "text": unsorted_contents,
                        },
                    ],
                }
            )
            open_done.wait(TIMEOUT)
            assert len(open_results) >= 1

            # Now change the cell to sorted imports — diagnostics should clear.
            change_results, change_done = _collect_diagnostics(ls_session, count=1)
            ls_session.notify_notebook_did_change(
                {
                    "notebookDocument": {
                        "uri": notebook_uri,
                        "version": 1,
                    },
                    "change": {
                        "cells": {
                            "textContent": [
                                {
                                    "document": {
                                        "uri": cell_uri,
                                        "version": 2,
                                    },
                                    "changes": [
                                        {
                                            "range": {
                                                "start": {"line": 0, "character": 0},
                                                "end": {
                                                    "line": len(
                                                        unsorted_contents.splitlines()
                                                    ),
                                                    "character": 0,
                                                },
                                            },
                                            "text": sorted_contents,
                                        }
                                    ],
                                }
                            ],
                        },
                    },
                }
            )
            change_done.wait(TIMEOUT)

            cell_diag = next(r for r in change_results if r["uri"] == cell_uri)
            assert_that(cell_diag["diagnostics"], is_([]))


def test_notebook_did_change_structure_add_cell():
    """Adding a new cell with unsorted imports should lint it."""
    init_params = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
    init_params["initializationOptions"]["settings"][0]["check"] = True

    UNFORMATTED = constants.TEST_DATA / "sample2" / "sample.unformatted"
    FORMATTED = constants.TEST_DATA / "sample2" / "sample.formatted"
    sorted_contents = FORMATTED.read_text()
    unsorted_contents = UNFORMATTED.read_text()

    with utils.python_file("", UNFORMATTED.parent, ".ipynb") as pf:
        notebook_uri = _make_notebook_uri(pf)
        cell1_uri = _make_cell_uri(pf, "C00001")
        cell2_uri = _make_cell_uri(pf, "C00002")

        with session.LspSession() as ls_session:
            ls_session.initialize(init_params)

            # Open notebook with one sorted cell — no diagnostics expected.
            open_results, open_done = _collect_diagnostics(ls_session, count=1)
            ls_session.notify_notebook_did_open(
                {
                    "notebookDocument": {
                        "uri": notebook_uri,
                        "notebookType": "jupyter-notebook",
                        "version": 0,
                        "cells": [
                            {"kind": 2, "document": cell1_uri},
                        ],
                    },
                    "cellTextDocuments": [
                        {
                            "uri": cell1_uri,
                            "languageId": "python",
                            "version": 1,
                            "text": sorted_contents,
                        },
                    ],
                }
            )
            open_done.wait(TIMEOUT)

            # Add a new cell with unsorted imports via structure change.
            add_results, add_done = _collect_diagnostics(ls_session, count=1)
            ls_session.notify_notebook_did_change(
                {
                    "notebookDocument": {
                        "uri": notebook_uri,
                        "version": 1,
                    },
                    "change": {
                        "cells": {
                            "structure": {
                                "array": {
                                    "start": 1,
                                    "deleteCount": 0,
                                    "cells": [
                                        {"kind": 2, "document": cell2_uri},
                                    ],
                                },
                                "didOpen": [
                                    {
                                        "uri": cell2_uri,
                                        "languageId": "python",
                                        "version": 1,
                                        "text": unsorted_contents,
                                    },
                                ],
                            },
                        },
                    },
                }
            )
            add_done.wait(TIMEOUT)

            cell2_diag = next(r for r in add_results if r["uri"] == cell2_uri)
            assert_that(len(cell2_diag["diagnostics"]), is_(1))
            assert_that(cell2_diag["diagnostics"][0]["code"], is_("E"))


def test_notebook_did_save():
    """Saving a notebook should re-lint all cells."""
    init_params = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
    init_params["initializationOptions"]["settings"][0]["check"] = True

    UNFORMATTED = constants.TEST_DATA / "sample2" / "sample.unformatted"
    contents = UNFORMATTED.read_text()

    with utils.python_file("", UNFORMATTED.parent, ".ipynb") as pf:
        notebook_uri = _make_notebook_uri(pf)
        cell_uri = _make_cell_uri(pf, "C00001")

        with session.LspSession() as ls_session:
            ls_session.initialize(init_params)

            # Open notebook first.
            open_results, open_done = _collect_diagnostics(ls_session, count=1)
            ls_session.notify_notebook_did_open(
                {
                    "notebookDocument": {
                        "uri": notebook_uri,
                        "notebookType": "jupyter-notebook",
                        "version": 0,
                        "cells": [
                            {"kind": 2, "document": cell_uri},
                        ],
                    },
                    "cellTextDocuments": [
                        {
                            "uri": cell_uri,
                            "languageId": "python",
                            "version": 1,
                            "text": contents,
                        },
                    ],
                }
            )
            open_done.wait(TIMEOUT)

            # Save notebook — should re-lint.
            save_results, save_done = _collect_diagnostics(ls_session, count=1)
            ls_session.notify_notebook_did_save(
                {
                    "notebookDocument": {
                        "uri": notebook_uri,
                    },
                }
            )
            save_done.wait(TIMEOUT)

            assert len(save_results) >= 1
            cell_diag = next(r for r in save_results if r["uri"] == cell_uri)
            assert_that(len(cell_diag["diagnostics"]), is_(1))
            assert_that(cell_diag["diagnostics"][0]["code"], is_("E"))


def test_notebook_did_close():
    """Closing a notebook should clear diagnostics for all cells."""
    init_params = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
    init_params["initializationOptions"]["settings"][0]["check"] = True

    UNFORMATTED = constants.TEST_DATA / "sample2" / "sample.unformatted"
    contents = UNFORMATTED.read_text()

    with utils.python_file("", UNFORMATTED.parent, ".ipynb") as pf:
        notebook_uri = _make_notebook_uri(pf)
        cell_uri = _make_cell_uri(pf, "C00001")

        with session.LspSession() as ls_session:
            ls_session.initialize(init_params)

            # Open notebook with unsorted imports — diagnostics published.
            open_results, open_done = _collect_diagnostics(ls_session, count=1)
            ls_session.notify_notebook_did_open(
                {
                    "notebookDocument": {
                        "uri": notebook_uri,
                        "notebookType": "jupyter-notebook",
                        "version": 0,
                        "cells": [
                            {"kind": 2, "document": cell_uri},
                        ],
                    },
                    "cellTextDocuments": [
                        {
                            "uri": cell_uri,
                            "languageId": "python",
                            "version": 1,
                            "text": contents,
                        },
                    ],
                }
            )
            open_done.wait(TIMEOUT)
            assert len(open_results) >= 1

            # Close notebook — diagnostics should be cleared.
            close_results, close_done = _collect_diagnostics(ls_session, count=1)
            ls_session.notify_notebook_did_close(
                {
                    "notebookDocument": {
                        "uri": notebook_uri,
                    },
                    "cellTextDocuments": [
                        {
                            "uri": cell_uri,
                            "languageId": "python",
                            "version": 1,
                            "text": contents,
                        },
                    ],
                }
            )
            close_done.wait(TIMEOUT)

            cell_diag = next(r for r in close_results if r["uri"] == cell_uri)
            assert_that(cell_diag["diagnostics"], is_([]))
