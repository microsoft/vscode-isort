// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

// Thin wrapper: delegates to vscode-common-python-lsp shared package.

import { ConfigurationChangeEvent, WorkspaceFolder } from 'vscode';
import {
    IBaseSettings,
    checkIfConfigurationChanged as _checkIfConfigurationChanged,
    getGlobalSettings as _getGlobalSettings,
    getWorkspaceSettings as _getWorkspaceSettings,
    expandTilde,
} from '@vscode/common-python-lsp';
import { ISORT_TOOL_CONFIG } from './constants';
import { traceLog } from './logging';
import { getInterpreterDetails } from './python';
import { getConfiguration, getWorkspaceFolders } from './vscodeapi';

export interface ISettings extends IBaseSettings {
    check: boolean;
    severity: Record<string, string>;
    extraPaths: string[];
}

export function getExtensionSettings(namespace: string, includeInterpreter?: boolean): Promise<ISettings[]> {
    return Promise.all(getWorkspaceFolders().map((w) => getWorkspaceSettings(namespace, w, includeInterpreter)));
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

export async function getWorkspaceSettings(
    namespace: string,
    workspace: WorkspaceFolder,
    includeInterpreter?: boolean,
): Promise<ISettings> {
    const resolveInterpreter = includeInterpreter ? getInterpreterDetails : undefined;
    const settings = (await _getWorkspaceSettings(
        namespace,
        workspace,
        ISORT_TOOL_CONFIG,
        resolveInterpreter,
    )) as ISettings;

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

export async function getGlobalSettings(namespace: string, includeInterpreter?: boolean): Promise<ISettings> {
    const resolveInterpreter = includeInterpreter ? async () => getInterpreterDetails() : undefined;
    return (await _getGlobalSettings(namespace, ISORT_TOOL_CONFIG, resolveInterpreter)) as ISettings;
}

export function checkIfConfigurationChanged(e: ConfigurationChangeEvent, namespace: string): boolean {
    return (
        _checkIfConfigurationChanged(e, namespace, ISORT_TOOL_CONFIG.trackedSettings) ||
        e.affectsConfiguration('python.analysis.extraPaths')
    );
}

export function getServerEnabled(namespace: string): boolean {
    const config = getConfiguration(namespace);
    return config.get<boolean>('serverEnabled', true);
}
