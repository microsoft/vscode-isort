// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import {
    CancellationToken,
    CodeAction,
    CodeActionContext,
    CodeActionKind,
    CodeActionProvider,
    Command,
    Diagnostic,
    DiagnosticCollection,
    Disposable,
    languages,
    Range,
    Selection,
    TextDocument,
    Uri,
    workspace,
} from 'vscode';
import { traceWarn } from './logging';
import { diagnosticRunner, textEditRunner } from './runner';
import { getDocumentSelector } from './utilities';

export const notebookCellScheme = 'vscode-notebook-cell';
export const interactiveInputScheme = 'vscode-interactive-input';
export const interactiveScheme = 'vscode-interactive';

function isNotebookCell(uri: Uri): boolean {
    return (
        uri.scheme.includes(notebookCellScheme) ||
        uri.scheme.includes(interactiveInputScheme) ||
        uri.scheme.includes(interactiveScheme)
    );
}

let disposables: Disposable[] = [];
export function unRegisterSortImportFeatures(): void {
    disposables.forEach((d) => {
        try {
            d.dispose();
        } catch {}
    });
    disposables = [];
}

class CodeActionWithData extends CodeAction {
    public data?: string;
}

class SortImportsCodeActionProvider implements CodeActionProvider<CodeAction> {
    constructor(private readonly serverId: string) {}
    async provideCodeActions(
        document: TextDocument,
        _range: Range | Selection,
        context: CodeActionContext,
        _token: CancellationToken,
    ): Promise<(CodeAction | Command)[]> {
        const codeActions: (CodeAction | Command)[] = [];
        if (document.uri.fsPath.includes('site-packages')) {
            traceWarn('Skipping site-packages file: ', document.uri.fsPath);
            return codeActions;
        }
        if (isNotebookCell(document.uri)) {
            traceWarn('Skipping notebook cell (not supported in server-less mode: ', document.uri.fsPath);
            return codeActions;
        }

        const action1 = new CodeActionWithData('isort: Organize Imports', CodeActionKind.SourceOrganizeImports);
        action1.data = document.uri.fsPath;
        codeActions.push(action1);

        const diagnostics = context.diagnostics.filter((d) => d.source === 'isort' && d.code === 'E');
        if (diagnostics.length > 0) {
            const action2 = new CodeActionWithData(
                'isort: Fix import sorting and/or formatting',
                CodeActionKind.QuickFix,
            );
            action2.data = document.uri.fsPath;
            codeActions.push(action2);
        }

        return codeActions;
    }

    async resolveCodeAction(codeAction: CodeActionWithData, _token: CancellationToken): Promise<CodeAction> {
        const docs = workspace.textDocuments.filter((d) => d.uri.fsPath === codeAction.data);
        if (docs.length === 1) {
            codeAction.edit = await textEditRunner(this.serverId, docs[0]);
        }
        return codeAction;
    }
}

class SortImportsDiagnosticProvider implements Disposable {
    private diagnosticColl: DiagnosticCollection;

    constructor() {
        this.diagnosticColl = languages.createDiagnosticCollection('isort');
    }

    public publishDiagnostics(uri: Uri, diagnostics: Diagnostic[]) {
        if (diagnostics.length === 0) {
            this.diagnosticColl.delete(uri);
        } else {
            this.diagnosticColl.set(uri, diagnostics);
        }
    }

    dispose() {
        this.diagnosticColl.dispose();
    }
}

function runDiagnosticsOnStartup(serverId: string, provider: SortImportsDiagnosticProvider) {
    return Promise.all(
        workspace.textDocuments.map((td) => {
            if (td.languageId === 'python') {
                return diagnosticRunner(serverId, td)
                    .then((diagnostics) => {
                        provider.publishDiagnostics(td.uri, diagnostics);
                    })
                    .then(
                        () => {},
                        () => {},
                    );
            }
        }),
    );
}

export function registerSortImportFeatures(serverId: string): Disposable & { startup: () => Promise<void> } {
    unRegisterSortImportFeatures();

    const diagnosticsProvider = new SortImportsDiagnosticProvider();
    disposables.push(
        languages.registerCodeActionsProvider(getDocumentSelector(), new SortImportsCodeActionProvider(serverId), {
            providedCodeActionKinds: [CodeActionKind.SourceOrganizeImports, CodeActionKind.QuickFix],
        }),
        workspace.onDidCloseTextDocument((td: TextDocument) => {
            diagnosticsProvider.publishDiagnostics(td.uri, []);
        }),
        workspace.onDidOpenTextDocument(async (td: TextDocument) => {
            if (td.languageId === 'python') {
                const diagnostics = await diagnosticRunner(serverId, td);
                diagnosticsProvider.publishDiagnostics(td.uri, diagnostics);
            }
        }),
        workspace.onDidSaveTextDocument(async (td: TextDocument) => {
            if (td.languageId === 'python') {
                const diagnostics = await diagnosticRunner(serverId, td);
                diagnosticsProvider.publishDiagnostics(td.uri, diagnostics);
            }
        }),
        diagnosticsProvider,
    );

    return {
        dispose: function () {
            unRegisterSortImportFeatures();
        },
        startup: async function (): Promise<void> {
            await runDiagnosticsOnStartup(serverId, diagnosticsProvider);
        },
    };
}
