"""
Test for path and interpreter settings.
"""

import copy
import pathlib
import sys
from unittest.mock import MagicMock

from hamcrest import assert_that, is_

from .lsp_test_client import constants, defaults, session, utils

# Add bundled paths so lsp_server and its deps can be imported
_PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "bundled" / "libs"))
sys.path.insert(0, str(_PROJECT_ROOT / "bundled" / "tool"))

from lsp_server import _get_document_path

TEST_FILE = constants.TEST_DATA / "sample1" / "sample.py"


class CallbackObject:
    """Object that holds results for WINDOW_LOG_MESSAGE to capture argv"""

    def __init__(self):
        self.result = False

    def check_result(self):
        """returns Boolean result"""
        return self.result

    def check_for_argv_duplication(self, argv):
        """checks if argv duplication exists and sets result boolean"""
        if argv["type"] == 4 and argv["message"].split().count("--from-stdin") > 1:
            self.result = True


def test_path():
    """Test linting using isort bin path set."""

    init_params = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
    init_params["initializationOptions"]["settings"][0]["path"] = ["isort"]

    argv_callback_object = CallbackObject()
    contents = TEST_FILE.read_text()

    actual = []
    with utils.python_file(contents, TEST_FILE.parent) as file:
        uri = utils.as_uri(str(file))

        with session.LspSession() as ls_session:
            ls_session.set_notification_callback(
                session.WINDOW_LOG_MESSAGE,
                argv_callback_object.check_for_argv_duplication,
            )

            ls_session.initialize(init_params)
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

            # Call this second time to detect arg duplication.
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

            actual = argv_callback_object.check_result()

    assert_that(actual, is_(False))


def test_interpreter():
    """Test linting using specific python path."""
    init_params = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
    init_params["initializationOptions"]["settings"][0]["interpreter"] = ["python"]

    argv_callback_object = CallbackObject()
    contents = TEST_FILE.read_text()

    actual = []
    with utils.python_file(contents, TEST_FILE.parent) as file:
        uri = utils.as_uri(str(file))

        with session.LspSession() as ls_session:
            ls_session.set_notification_callback(
                session.WINDOW_LOG_MESSAGE,
                argv_callback_object.check_for_argv_duplication,
            )

            ls_session.initialize(init_params)
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

            # Call this second time to detect arg duplication.
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

            actual = argv_callback_object.check_result()

    assert_that(actual, is_(False))


def test_notebook_document_path():
    """Test resolving notebook cell paths."""
    document = MagicMock()
    document.uri = "vscode-notebook-cell:/path/to/notebook.ipynb#C00001"
    document.path = "/fallback/path.py"

    path = _get_document_path(document)

    assert_that(pathlib.Path(path), is_(pathlib.Path("/path/to/notebook.ipynb")))
