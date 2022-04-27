# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Implementation of formatting support over LSP.
"""
import ast
import json
import os
import pathlib
import sys
import traceback
from typing import List, Optional, Sequence, Union

# Ensure that we can import LSP libraries, and other bundled formatter libraries
sys.path.append(str(pathlib.Path(__file__).parent.parent / "libs"))

import utils
from pygls import lsp, protocol, server, uris, workspace
from pygls.lsp import types

FORMATTER = {
    "name": "isort",
    "module": "isort",
    "args": [],
}
WORKSPACE_SETTINGS = {}
RUNNER = pathlib.Path(__file__).parent / "runner.py"

MAX_WORKERS = 5
LSP_SERVER = server.LanguageServer(max_workers=MAX_WORKERS)


def is_python(code: str) -> bool:
    """Ensures that the code provided is python."""
    try:
        ast.parse(code)
    except SyntaxError:
        return False
    return True


def _filter_args(args: List[str]) -> List[str]:
    """
    Removes arguments that prevent isort from formatting or can cause
    errors when parsing output.
    """
    return [
        a
        for a in args
        if a not in ["--diff", "-h", "--help", "--version", "--overwrite-in-place"]
    ]


def _get_line_endings(lines: List[str]) -> str:
    """Returns line endings used in the text."""
    try:
        if lines[0][-2:] == "\r\n":
            return "\r\n"
        return "\n"
    except Exception:
        return None


def _match_line_endings(document: workspace.Document, text: str) -> str:
    """Ensures that the edited text line endings matches the document line endings."""
    expected = _get_line_endings(document.source.splitlines(keepends=True))
    actual = _get_line_endings(text.splitlines(keepends=True))
    if actual == expected or actual is None or expected is None:
        return text
    return text.replace(actual, expected)


def _update_workspace_settings(settings):
    for setting in settings:
        key = uris.to_fs_path(setting["workspace"])
        WORKSPACE_SETTINGS[key] = {
            **setting,
            "workspaceFS": key,
        }


def _get_settings_by_document(document: workspace.Document):
    if len(WORKSPACE_SETTINGS) == 1 or document.path is None:
        return list(WORKSPACE_SETTINGS.values())[0]

    document_workspace = pathlib.Path(document.path)
    workspaces = [s["workspaceFS"] for s in WORKSPACE_SETTINGS.values()]

    while document_workspace != document_workspace.parent:
        if str(document_workspace) in workspaces:
            break
        document_workspace = document_workspace.parent

    return WORKSPACE_SETTINGS[str(document_workspace)]


def _run(
    document: workspace.Document, extra_args: Sequence[str], default: str
) -> utils.RunResult:
    if utils.is_stdlib_file(document.path):
        # Don't format standard library python files.
        return None

    settings = _get_settings_by_document(document)

    module = FORMATTER["module"]
    cwd = settings["workspaceFS"]

    if len(settings["path"]) > 0:
        # 'path' setting takes priority over everything.
        use_path = True
        argv = settings["path"]
    elif len(settings["interpreter"]) > 0 and not utils.is_current_interpreter(
        settings["interpreter"][0]
    ):
        # If there is a different interpreter set use that interpreter.
        argv = settings["interpreter"] + [str(RUNNER), module]
        use_path = True
    else:
        # if the interpreter is same as the interpreter running this
        # process then run as module.
        argv = [FORMATTER["module"]]
        use_path = False

    argv += _filter_args(FORMATTER["args"] + settings["args"])
    argv += extra_args
    argv += ["--filename", document.path, "-"] if document.path else ["-"]

    LSP_SERVER.show_message_log(" ".join(argv))
    LSP_SERVER.show_message_log(f"CWD Formatter: {cwd}")

    # Force line endings to be `\n`, this makes the diff
    # easier to work with
    source = document.source.replace("\r\n", "\n")

    try:
        if use_path:
            result = utils.run_path(argv=argv, use_stdin=True, cwd=cwd, source=source)
        else:
            result = utils.run_module(
                module=module, argv=argv, use_stdin=True, cwd=cwd, source=source
            )
        return result
    except Exception:
        error_text = traceback.format_exc()
        LSP_SERVER.show_message_log(error_text, msg_type=types.MessageType.Error)
        LSP_SERVER.show_message(
            f"Formatting error, please see Output > isort for more info:\r\n{error_text}",
            msg_type=types.MessageType.Error,
        )
    return utils.RunResult(default, None)


def _publish_diagnostics(
    server: server.LanguageServer, params: types.DidOpenTextDocumentParams
):
    document = server.workspace.get_document(params.text_document.uri)
    result = _run(document, extra_args=["--check"], default="")

    if result:
        has_error = any(
            [
                line.startswith("ERROR")
                for line in result.stderr.splitlines(keepends=False)
            ]
        )
    else:
        has_error = False

    diagnostics = []
    if has_error:
        try:
            import_line = [
                i
                for i, l in enumerate(document.lines)
                if l.startswith("import") or l.startswith("from")
            ][0]
        except IndexError:
            import_line = 0

        diagnostics.append(
            types.Diagnostic(
                range=types.Range(
                    start=types.Position(
                        line=import_line,
                        character=0,
                    ),
                    end=types.Position(
                        line=import_line + 1,
                        character=0,
                    ),
                ),
                message="Imports are incorrectly sorted and/or formatted.",
                severity=types.DiagnosticSeverity.Error,
                code="E",
                source="isort",
            )
        )

    server.publish_diagnostics(document.uri, diagnostics=diagnostics)


def _format(document: workspace.Document) -> Union[List[types.TextEdit], None]:
    """Runs formatter, processes the output, and returns text edits."""
    result = _run(document, extra_args=[], default=document.source)

    if result.stderr:
        LSP_SERVER.show_message_log(result.stderr, msg_type=types.MessageType.Error)
        if result.stderr.find("Error:") >= 0 or result.stderr.find("error:") >= 0:
            LSP_SERVER.show_message(
                f"Formatting error, please see Output > isort for more info:\r\n{result.stderr}",
                msg_type=types.MessageType.Error,
            )
            return None

    new_source = _match_line_endings(document, result.stdout)

    # Skip last line ending in a notebook cell
    if document.uri.startswith("vscode-notebook-cell"):
        if new_source.endswith("\r\n"):
            new_source = new_source[:-2]
        elif new_source.endswith("\n"):
            new_source = new_source[:-1]

    if new_source == document.source:
        return None

    return [
        types.TextEdit(
            range=types.Range(
                start=types.Position(line=0, character=0),
                end=types.Position(line=len(document.lines), character=0),
            ),
            new_text=new_source,
        )
    ]


def _create_workspace_edits(
    document: workspace.Document, results: Optional[List[lsp.TextEdit]]
):
    return lsp.WorkspaceEdit(
        document_changes=[
            lsp.TextDocumentEdit(
                text_document=lsp.VersionedTextDocumentIdentifier(
                    uri=document.uri,
                    version=0 if document.version is None else document.version,
                ),
                edits=results,
            )
        ],
    )


@LSP_SERVER.feature(lsp.INITIALIZE)
def initialize(params: types.InitializeParams):
    """LSP handler for initialize request."""
    LSP_SERVER.show_message_log(f"CWD Format Server: {os.getcwd()}")

    paths = "\r\n    ".join(sys.path)
    LSP_SERVER.show_message_log(f"sys.path used to run Formatter:\r\n    {paths}\r\n")

    settings = params.initialization_options["settings"]
    _update_workspace_settings(settings)
    LSP_SERVER.show_message_log(
        f"Settings used to run Formatter:\r\n{json.dumps(settings, indent=4, ensure_ascii=False)}\r\n"
    )

    if isinstance(LSP_SERVER.lsp, protocol.LanguageServerProtocol):
        trace = lsp.Trace.Off
        for setting in settings:
            if setting["trace"] == "debug":
                trace = lsp.Trace.Verbose
                break
            if setting["trace"] == "off":
                continue
            trace = lsp.Trace.Messages
        LSP_SERVER.lsp.trace = trace


@LSP_SERVER.feature(
    lsp.CODE_ACTION,
    lsp.CodeActionOptions(
        code_action_kinds=[
            lsp.CodeActionKind.SourceOrganizeImports,
            lsp.CodeActionKind.QuickFix,
        ],
        resolve_provider=True,
    ),
)
def organize(server: server.LanguageServer, params: lsp.CodeActionParams):
    text_document = server.workspace.get_document(params.text_document.uri)

    if utils.is_stdlib_file(text_document.path):
        # Don't format standard library python files.
        # Publishing empty diagnostics clears the entry
        return None

    if (
        params.context.only
        and len(params.context.only) == 1
        and lsp.CodeActionKind.SourceOrganizeImports in params.context.only
    ):
        # This is triggered with users run the Organize Imports command from
        # VS Code. The `context.only` field will have one item that is the
        # `SourceOrganizeImports` code action.
        results = _format(text_document)
        if results:
            # Clear out diagnostics, since we are making changes to address
            # import sorting issues.
            server.publish_diagnostics(text_document.uri, [])
            return [
                lsp.CodeAction(
                    title="isort: Organize Imports",
                    kind=lsp.CodeActionKind.SourceOrganizeImports,
                    data=params.text_document.uri,
                    edit=_create_workspace_edits(text_document, results),
                )
            ]

    diagnostics = [
        d for d in params.context.diagnostics if d.source == "isort" and d.code == "E"
    ]
    return [
        lsp.CodeAction(
            title="isort: Organize Imports",
            kind=lsp.CodeActionKind.SourceOrganizeImports,
            data=params.text_document.uri,
            edit=None,
        ),
        lsp.CodeAction(
            title="isort: Fix import sorting and/or formatting",
            kind=lsp.CodeActionKind.QuickFix,
            data=params.text_document.uri,
            edit=None,
            diagnostics=diagnostics if diagnostics else None,
        ),
    ]


@LSP_SERVER.feature(lsp.CODE_ACTION_RESOLVE)
def resolve(server: server.LanguageServer, params: lsp.CodeAction):
    text_document = server.workspace.get_document(params.data)

    results = _format(text_document)

    if results:
        # Clear out diagnostics, since we are making changes to address
        # import sorting issues.
        server.publish_diagnostics(text_document.uri, [])
    else:
        # There are no changes so return the original code as is.
        # This could be due to error while running import sorter
        # so, don't clearout the diagnostics.
        results = [
            types.TextEdit(
                range=types.Range(
                    start=types.Position(line=0, character=0),
                    end=types.Position(line=len(text_document.lines), character=0),
                ),
                new_text=text_document.source,
            )
        ]

    params.edit = _create_workspace_edits(text_document, results)
    return params


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def did_open(server: server.LanguageServer, params: types.DidOpenTextDocumentParams):
    _publish_diagnostics(server, params)


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
def did_save(server: server.LanguageServer, params: types.DidSaveTextDocumentParams):
    _publish_diagnostics(server, params)


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
def did_close(server: server.LanguageServer, params: types.DidCloseTextDocumentParams):
    # Publishing empty diagnostics to clear the entries for this file.
    text_document = server.workspace.get_document(params.text_document.uri)
    server.publish_diagnostics(text_document.uri, [])


if __name__ == "__main__":
    LSP_SERVER.start_io()
