// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

// Thin wrapper: delegates to vscode-common-python-lsp shared package.
// Defines ISettings (extends IBaseSettings with isort-specific fields)
// and provides backward-compatible function signatures.

import { ConfigurationChangeEvent, WorkspaceFolder } from 'vscode';
import {
    IBaseSettings,
    checkIfConfigurationChanged as _checkIfConfigurationChanged,
    getGlobalSettings as _getGlobalSettings,
    getWorkspaceSettings as _getWorkspaceSettings,
} from '@vscode/common-python-lsp';
import { ISORT_TOOL_CONFIG } from './constants';
import { traceWarn } from './logging';
import { getInterpreterDetails } from './python';
import { getConfiguration, getWorkspaceFolders } from './vscodeapi';

export interface ISettings extends IBaseSettings {
    check: boolean;
    severity: Record<string, string>;
    extraPaths: string[];
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

    return settings;
}

export function getExtensionSettings(namespace: string, includeInterpreter?: boolean): Promise<ISettings[]> {
    return Promise.all(getWorkspaceFolders().map((w) => getWorkspaceSettings(namespace, w, includeInterpreter)));
}

export async function getGlobalSettings(namespace: string, includeInterpreter?: boolean): Promise<ISettings> {
    const resolveInterpreter = includeInterpreter ? async () => getInterpreterDetails() : undefined;
    const settings = (await _getGlobalSettings(namespace, ISORT_TOOL_CONFIG, resolveInterpreter)) as ISettings;

    // Preserve old behavior: when includeInterpreter is false, interpreter is []
    if (!includeInterpreter) {
        settings.interpreter = [];
    }

    return settings;
}

export function checkIfConfigurationChanged(e: ConfigurationChangeEvent, namespace: string): boolean {
    return _checkIfConfigurationChanged(e, namespace, ISORT_TOOL_CONFIG.trackedSettings);
}

export function getServerEnabled(namespace: string): boolean {
    const config = getConfiguration(namespace);
    return config.get<boolean>('serverEnabled', true);
}

// Legacy settings logging for isort's python.sortImports.* settings
export function logLegacySettings(): void {
    getWorkspaceFolders().forEach((workspace) => {
        try {
            const legacyConfig = getConfiguration('python', workspace.uri);

            const legacyArgs = legacyConfig.get<string[]>('sortImports.args', []);
            if (legacyArgs.length > 0) {
                traceWarn(`"python.sortImports.args" is deprecated. Use "isort.args" instead.`);
                traceWarn(`"python.sortImports.args" value for workspace ${workspace.uri.fsPath}:`);
                traceWarn(`\n${JSON.stringify(legacyArgs, null, 4)}`);
            }

            const legacyPath = legacyConfig.get<string>('sortImports.path', '');
            if (legacyPath.length > 0 && legacyPath !== 'isort') {
                traceWarn(`"python.sortImports.path" is deprecated. Use "isort.path" instead.`);
                traceWarn(`"python.sortImports.path" value for workspace ${workspace.uri.fsPath}:`);
                traceWarn(`\n${JSON.stringify(legacyPath, null, 4)}`);
            }
        } catch (err) {
            traceWarn(`Error while logging legacy settings: ${err}`);
        }
    });
}
