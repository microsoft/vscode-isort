# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unit tests for the get_cwd() helper in lsp_server."""

import os
import pathlib
import sys
import types


# ---------------------------------------------------------------------------
# Stub out bundled LSP dependencies so lsp_server can be imported without the
# full VS Code extension environment.
# ---------------------------------------------------------------------------
def _setup_mocks():
    class _MockLS:
        def __init__(self, **kwargs):
            pass

        def feature(self, *args, **kwargs):
            return lambda f: f

        def command(self, *args, **kwargs):
            return lambda f: f

        def show_message_log(self, *args, **kwargs):
            pass

        def show_message(self, *args, **kwargs):
            pass

    mock_server = types.ModuleType("pygls.lsp.server")
    mock_server.LanguageServer = _MockLS

    mock_workspace = types.ModuleType("pygls.workspace")
    mock_workspace.TextDocument = type("TextDocument", (), {"path": None, "uri": None})

    mock_pygls = types.ModuleType("pygls")
    mock_pygls_uris = types.ModuleType("pygls.uris")
    mock_pygls_uris.from_fs_path = lambda p: "file://" + p
    mock_pygls_uris.to_fs_path = lambda u: u.replace("file://", "")

    mock_lsp = types.ModuleType("lsprotocol.types")
    for _name in [
        "CODE_ACTION_RESOLVE",
        "EXIT",
        "INITIALIZE",
        "SHUTDOWN",
        "TEXT_DOCUMENT_CODE_ACTION",
        "TEXT_DOCUMENT_DID_CLOSE",
        "TEXT_DOCUMENT_DID_OPEN",
        "TEXT_DOCUMENT_DID_SAVE",
        "TEXT_DOCUMENT_FORMATTING",
    ]:
        setattr(mock_lsp, _name, _name)
    for _name in [
        "CodeActionOptions",
        "CodeActionParams",
        "Diagnostic",
        "DiagnosticSeverity",
        "DidCloseTextDocumentParams",
        "DidOpenTextDocumentParams",
        "DidSaveTextDocumentParams",
        "InitializeParams",
        "LogMessageParams",
        "Position",
        "PublishDiagnosticsParams",
        "Range",
        "TextDocumentEdit",
        "TextEdit",
        "TraceValue",
        "VersionedTextDocumentIdentifier",
        "WorkspaceEdit",
    ]:
        setattr(mock_lsp, _name, type(_name, (), {"__init__": lambda self, **kw: None}))
    mock_lsp.CodeActionKind = type(
        "CodeActionKind",
        (),
        {"SourceOrganizeImports": "source.organizeImports", "QuickFix": "quickfix"},
    )
    mock_lsp.MessageType = type(
        "MessageType", (), {"Log": 4, "Error": 1, "Warning": 2, "Info": 3}
    )

    mock_lsp_jsonrpc = types.ModuleType("lsp_jsonrpc")
    mock_lsp_jsonrpc.shutdown_json_rpc = lambda: None
    mock_lsp_jsonrpc.start_json_rpc = lambda *a, **kw: None
    mock_lsp_jsonrpc.send_response = lambda *a, **kw: None
    mock_lsp_jsonrpc.send_notification = lambda *a, **kw: None
    mock_lsp_jsonrpc.JsonRPCException = Exception

    mock_lsp_utils = types.ModuleType("lsp_utils")
    mock_lsp_utils.is_stdlib_file = lambda *a, **kw: False
    mock_lsp_utils.normalize_path = lambda p: str(p)
    mock_lsp_utils.RunResult = type("RunResult", (), {})

    mock_isort = types.ModuleType("isort")

    mock_pygls.lsp = types.ModuleType("pygls.lsp")
    mock_pygls.workspace = mock_workspace
    mock_pygls.uris = mock_pygls_uris

    for _mod_name, _mod in [
        ("pygls", mock_pygls),
        ("pygls.lsp", mock_pygls.lsp),
        ("pygls.lsp.server", mock_server),
        ("pygls.workspace", mock_workspace),
        ("pygls.uris", mock_pygls_uris),
        ("lsprotocol", types.ModuleType("lsprotocol")),
        ("lsprotocol.types", mock_lsp),
        ("lsp_jsonrpc", mock_lsp_jsonrpc),
        ("lsp_utils", mock_lsp_utils),
        ("isort", mock_isort),
    ]:
        if _mod_name not in sys.modules:
            sys.modules[_mod_name] = _mod

    tool_dir = str(pathlib.Path(__file__).parents[3] / "bundled" / "tool")
    if tool_dir not in sys.path:
        sys.path.insert(0, tool_dir)


_setup_mocks()

import lsp_server  # noqa: E402

WORKSPACE = "/home/user/myproject"


def _make_settings(cwd=None):
    s = {"workspaceFS": WORKSPACE}
    if cwd is not None:
        s["cwd"] = cwd
    return s


def _make_doc(path):
    """Create a mock TextDocument with path and uri attributes."""
    return types.SimpleNamespace(path=path, uri="file://" + path)


# ---------------------------------------------------------------------------
# No-document (fallback) cases
# ---------------------------------------------------------------------------


def test_no_cwd_no_document_returns_workspace():
    """When neither cwd nor document is provided, return workspaceFS."""
    settings = _make_settings()
    assert lsp_server.get_cwd(settings, None) == WORKSPACE


def test_plain_cwd_no_document_returned_unchanged():
    """A cwd without variables is returned as-is even without a document."""
    settings = _make_settings(cwd="/custom/path")
    assert lsp_server.get_cwd(settings, None) == "/custom/path"


def test_file_variable_no_document_falls_back_to_workspace():
    """Unresolvable ${file*} variable with no document falls back to workspaceFS."""
    for token in [
        "${file}",
        "${fileBasename}",
        "${fileBasenameNoExtension}",
        "${fileExtname}",
        "${fileDirname}",
        "${fileDirnameBasename}",
        "${fileWorkspaceFolder}",
    ]:
        settings = _make_settings(cwd=token + "/extra")
        assert lsp_server.get_cwd(settings, None) == WORKSPACE, f"Failed for {token}"


def test_relative_file_variable_no_document_falls_back_to_workspace():
    """Unresolvable ${relativeFile*} variable with no document falls back to workspaceFS."""
    for token in ["${relativeFile}", "${relativeFileDirname}"]:
        settings = _make_settings(cwd=token)
        assert lsp_server.get_cwd(settings, None) == WORKSPACE, f"Failed for {token}"


# ---------------------------------------------------------------------------
# With document
# ---------------------------------------------------------------------------

DOC_PATH = "/home/user/myproject/src/foo.py"
DOC = _make_doc(DOC_PATH)


def test_file_resolved():
    settings = _make_settings(cwd="${file}")
    assert lsp_server.get_cwd(settings, DOC) == DOC_PATH


def test_file_basename_resolved():
    settings = _make_settings(cwd="${fileBasename}")
    assert lsp_server.get_cwd(settings, DOC) == "foo.py"


def test_file_basename_no_extension_resolved():
    settings = _make_settings(cwd="${fileBasenameNoExtension}")
    assert lsp_server.get_cwd(settings, DOC) == "foo"


def test_file_extname_resolved():
    settings = _make_settings(cwd="${fileExtname}")
    assert lsp_server.get_cwd(settings, DOC) == ".py"


def test_file_dirname_resolved():
    settings = _make_settings(cwd="${fileDirname}")
    assert lsp_server.get_cwd(settings, DOC) == "/home/user/myproject/src"


def test_file_dirname_basename_resolved():
    settings = _make_settings(cwd="${fileDirnameBasename}")
    assert lsp_server.get_cwd(settings, DOC) == "src"


def test_relative_file_resolved():
    settings = _make_settings(cwd="${relativeFile}")
    assert lsp_server.get_cwd(settings, DOC) == os.path.relpath(DOC_PATH, WORKSPACE)


def test_relative_file_dirname_resolved():
    settings = _make_settings(cwd="${relativeFileDirname}")
    assert lsp_server.get_cwd(settings, DOC) == os.path.relpath(
        "/home/user/myproject/src", WORKSPACE
    )


def test_file_workspace_folder_resolved():
    settings = _make_settings(cwd="${fileWorkspaceFolder}")
    assert lsp_server.get_cwd(settings, DOC) == WORKSPACE


def test_composite_pattern_resolved():
    """Variables embedded inside a longer path are substituted correctly."""
    settings = _make_settings(cwd="${fileDirname}/subdir")
    assert lsp_server.get_cwd(settings, DOC) == "/home/user/myproject/src/subdir"


def test_multiple_variables_in_one_cwd():
    """Multiple different variables in the same cwd string are all resolved."""
    settings = _make_settings(cwd="${fileDirname}/${fileBasename}")
    result = lsp_server.get_cwd(settings, DOC)
    assert result == "/home/user/myproject/src/foo.py"


def test_no_variable_in_cwd_unchanged():
    """A cwd with no variables is returned unchanged even when a document exists."""
    settings = _make_settings(cwd="/static/path")
    assert lsp_server.get_cwd(settings, DOC) == "/static/path"


def test_document_with_no_path_falls_back_to_workspace():
    """A document object whose path is falsy triggers the fallback."""
    doc = types.SimpleNamespace(path="", uri="file://")
    settings = _make_settings(cwd="${fileDirname}")
    assert lsp_server.get_cwd(settings, doc) == WORKSPACE
