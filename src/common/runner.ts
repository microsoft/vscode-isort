// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as proc from 'child_process';
import {
    CancellationToken,
    Diagnostic,
    DiagnosticSeverity,
    EndOfLine,
    Position,
    Range,
    TextDocument,
    TextEdit,
    WorkspaceEdit,
} from 'vscode';
import { RUNNER_SCRIPT_PATH } from './constants';
import { traceError, traceLog } from './logging';
import { ISettings, getWorkspaceSettings } from './settings';
import { getProjectRoot } from './utilities';
import { getWorkspaceFolder } from './vscodeapi';

interface Result {
    stdout: string;
    stderr: string;
}

function runScript(
    runner: string,
    args: string[],
    options?: {
        ignoreError?: boolean;
        cwd?: string;
        newEnv?: { [x: string]: string | undefined };
    },
    input?: string,
    token?: CancellationToken,
): Promise<Result> {
    traceLog(runner, args.join(' '));
    traceLog(`CWD: ${options?.cwd}`);
    const promise = new Promise<Result>((resolve, reject) => {
        const scriptProc = proc.execFile(
            runner,
            args,
            {
                encoding: 'utf-8',
                env: options?.newEnv,
                cwd: options?.cwd,
            },
            (err, stdout, stderr) => {
                if (options?.ignoreError) {
                    resolve({ stdout, stderr });
                } else if (err) {
                    reject(err);
                } else {
                    resolve({ stdout, stderr });
                }
            },
        );
        if (input) {
            scriptProc.stdin?.end(input, 'utf-8');
        }
        token?.onCancellationRequested(() => {
            //resolve({ stdout: '', stderr: '' });
            //scriptProc.kill();
        });
    });

    return promise;
}

async function getSettings(serverId: string, textDocument: TextDocument): Promise<ISettings | undefined> {
    const workspaceFolder = getWorkspaceFolder(textDocument.uri) || (await getProjectRoot());
    const workspaceSetting = await getWorkspaceSettings(serverId, workspaceFolder, true);
    if (workspaceSetting.interpreter.length === 0) {
        traceError(
            'Python interpreter missing:\r\n' +
                '[Option 1] Select python interpreter using the ms-python.python.\r\n' +
                `[Option 2] Set an interpreter using "${serverId}.interpreter" setting.\r\n`,
        );
        return undefined;
    }

    return workspaceSetting;
}

function getExecutablePathWithArgs(settings: ISettings, extraArgs: string[] = []): string[] {
    if (settings.path.length > 0) {
        return [...settings.path, ...extraArgs, ...settings.args];
    }

    return [...settings.interpreter, RUNNER_SCRIPT_PATH, ...extraArgs, ...settings.args];
}

function getFirstImport(textDocument: TextDocument): number {
    const content = textDocument.getText();
    const lines = content.split(/\r?\n|\r|\n/g);
    let index = 0;
    for (const line of lines) {
        if (line.startsWith('import') || line.startsWith('from')) {
            return index;
        }
        index += 1;
    }
    return 0;
}

function getSeverity(sev: string): DiagnosticSeverity {
    switch (sev) {
        case 'Hint':
            return DiagnosticSeverity.Hint;
        case 'Error':
            return DiagnosticSeverity.Error;
        case 'Information':
            return DiagnosticSeverity.Information;
        case 'Warning':
            return DiagnosticSeverity.Warning;
    }
    return DiagnosticSeverity.Error;
}

function getUpdatedEnvVariables(settings: ISettings): { [x: string]: string | undefined } {
    const newEnv = { ...process.env };
    if (settings.path.length === 0) {
        newEnv.LS_IMPORT_STRATEGY = settings.importStrategy;
    }
    return newEnv;
}

export async function diagnosticRunner(serverId: string, textDocument: TextDocument): Promise<Diagnostic[]> {
    const diagnostics: Diagnostic[] = [];
    const settings = await getSettings(serverId, textDocument);

    if (settings && settings.check) {
        const parts = getExecutablePathWithArgs(settings);
        const args = parts.slice(1).concat('--check', textDocument.uri.fsPath);
        const newEnv = getUpdatedEnvVariables(settings);
        try {
            const { stderr } = await runScript(parts[0], args, { ignoreError: true, newEnv, cwd: settings.cwd });
            const lines = stderr.split(/\r?\n|\r|\n/g);
            for (const line of lines) {
                if (line.startsWith('ERROR') && line.toLowerCase().includes('imports are incorrectly sorted')) {
                    const lineNo = getFirstImport(textDocument);
                    diagnostics.push({
                        range: new Range(new Position(lineNo, 0), new Position(lineNo + 1, 0)),
                        message: 'Imports are incorrectly sorted and/or formatted.',
                        severity: getSeverity(settings.severity['E']),
                        source: 'isort',
                        code: 'E',
                    });
                }
            }
        } catch (err) {
            traceError(err);
        }
    }
    return diagnostics;
}

function fixLineEndings(eol: EndOfLine, formatted: string): string {
    const lines = formatted.replace(/\r\r\n/g, '\r\n').split(/\r?\n/g);
    const result = lines.join(eol === EndOfLine.CRLF ? '\r\n' : '\n');
    return result;
}

export async function textEditRunner(
    serverId: string,
    textDocument: TextDocument,
    token?: CancellationToken,
): Promise<WorkspaceEdit> {
    const settings = await getSettings(serverId, textDocument);
    const content = textDocument.getText();
    const lines = content.split(/\r?\n|\r|\n/g);
    if (settings) {
        let parts: string[] = [];
        let args: string[] = [];

        if (textDocument.isDirty || textDocument.isUntitled) {
            parts = getExecutablePathWithArgs(settings, ['-']);
            args = parts.slice(1).concat('--filename', textDocument.uri.fsPath);
        } else {
            parts = getExecutablePathWithArgs(settings);
            args = parts.slice(1).concat('--stdout', textDocument.uri.fsPath);
        }
        const newEnv = getUpdatedEnvVariables(settings);

        try {
            const { stdout } = await runScript(
                parts[0],
                args,
                { ignoreError: true, newEnv, cwd: settings.cwd },
                content,
            );
            const newContent = stdout.length === 0 ? content : fixLineEndings(textDocument.eol, stdout);
            const edits = new WorkspaceEdit();
            edits.replace(textDocument.uri, new Range(new Position(0, 0), new Position(lines.length, 0)), newContent);
            return edits;
        } catch (err) {
            traceError(err);
        }
    }
    const edits = new WorkspaceEdit();
    edits.set(textDocument.uri, [
        TextEdit.replace(new Range(new Position(0, 0), new Position(lines.length, 0)), content),
    ]);
    return edits;
}
