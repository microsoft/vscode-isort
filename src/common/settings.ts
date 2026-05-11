// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

// Extension-specific settings: ISettings type extension, serverEnabled toggle,
// and legacy settings logging. All shared settings resolution is handled by
// @vscode/common-python-lsp directly.

import { WorkspaceFolder } from 'vscode';
import {
    IBaseSettings,
    expandTilde,
    getConfiguration,
    getWorkspaceFolders,
    getWorkspaceSettings as _getWorkspaceSettings,
    traceLog,
} from '@vscode/common-python-lsp';
import { ISORT_TOOL_CONFIG } from './constants';

export interface ISettings extends IBaseSettings {
    check: boolean;
    severity: Record<string, string>;
    extraPaths: string[];
}

export function getServerEnabled(namespace: string): boolean {
    const config = getConfiguration(namespace);
    return config.get<boolean>('serverEnabled', true);
}

function getLegacyArgs(namespace: string, workspace: WorkspaceFolder): string[] | undefined {
    const config = getConfiguration(namespace, workspace.uri);
    const args = config.get<string[]>('args', []);
    if (args.length > 0) {
        return undefined; // primary setting is set, no fallback needed
    }

    const legacyConfig = getConfiguration('python', workspace.uri);
    const legacyArgs = legacyConfig.get<string[]>('sortImports.args', []);
    if (legacyArgs.length > 0) {
        traceLog(`Using legacy configuration form 'python.sortImports.args': ${legacyArgs.join(' ')}.`);
        return legacyArgs;
    }
    return undefined;
}

function getLegacyPath(namespace: string, workspace: WorkspaceFolder): string[] | undefined {
    const config = getConfiguration(namespace, workspace.uri);
    const path = config.get<string[]>('path', []);
    if (path.length > 0) {
        return undefined; // primary setting is set, no fallback needed
    }

    const legacyConfig = getConfiguration('python', workspace.uri);
    const legacyPath = legacyConfig.get<string>('sortImports.path', '');
    if (legacyPath.length > 0 && legacyPath !== 'isort') {
        traceLog(`Using legacy configuration form 'python.sortImports.path': ${legacyPath}`);
        return [legacyPath];
    }
    return undefined;
}

/**
 * Get workspace settings with isort-specific legacy fallbacks.
 * Used by runner.ts for local sort-import mode (when server is disabled).
 */
export async function getWorkspaceSettings(namespace: string, workspace: WorkspaceFolder): Promise<ISettings> {
    const settings = (await _getWorkspaceSettings(namespace, workspace, ISORT_TOOL_CONFIG)) as ISettings;

    // Legacy fallbacks for python.sortImports.args / python.sortImports.path
    const legacyArgs = getLegacyArgs(namespace, workspace);
    if (legacyArgs) {
        settings.args = legacyArgs;
    }
    const legacyPath = getLegacyPath(namespace, workspace);
    if (legacyPath) {
        settings.path = legacyPath;
    }

    // Expand tilde on path and extraPaths entries (shared handles cwd only)
    settings.path = settings.path.map(expandTilde);
    if (settings.extraPaths) {
        settings.extraPaths = settings.extraPaths.map(expandTilde);
    }

    return settings;
}

export function logLegacySettings(): void {
    getWorkspaceFolders().forEach((workspace) => {
        try {
            const legacyConfig = getConfiguration('python', workspace.uri);

            const legacyArgs = legacyConfig.get<string[]>('sortImports.args', []);
            if (legacyArgs.length > 0) {
                traceLog(`"python.sortImports.args" is deprecated. Use "isort.args" instead.`);
                traceLog(`"python.sortImports.args" value for workspace ${workspace.uri.fsPath}:`);
                traceLog(`\n${JSON.stringify(legacyArgs, null, 4)}`);
            }

            const legacyPath = legacyConfig.get<string>('sortImports.path', '');
            if (legacyPath.length > 0 && legacyPath !== 'isort') {
                traceLog(`"python.sortImports.path" is deprecated. Use "isort.path" instead.`);
                traceLog(`"python.sortImports.path" value for workspace ${workspace.uri.fsPath}:`);
                traceLog(`\n${JSON.stringify(legacyPath, null, 4)}`);
            }
        } catch (err) {
            traceLog(`Error while logging legacy settings: ${err}`);
        }
    });
}
