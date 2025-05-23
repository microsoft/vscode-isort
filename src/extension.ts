// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as vscode from 'vscode';
import { LanguageClient } from 'vscode-languageclient/node';
import { LS_SERVER_RESTART_DELAY, PYTHON_VERSION } from './common/constants';
import { registerLogger, traceError, traceLog, traceVerbose } from './common/logging';
import { initializePython, onDidChangePythonInterpreter } from './common/python';
import { restartServer } from './common/server';
import { ISettings, checkIfConfigurationChanged, getExtensionSettings, getWorkspaceSettings } from './common/settings';
import { loadServerDefaults } from './common/setup';
import { registerLanguageStatusItem, updateStatus } from './common/status';
import { getInterpreterFromSetting, getProjectRoot } from './common/utilities';
import { createOutputChannel, onDidChangeConfiguration, registerCommand } from './common/vscodeapi';

let lsClient: LanguageClient | undefined;
export async function activate(context: vscode.ExtensionContext): Promise<void> {
    // This is required to get server name and module. This should be
    // the first thing that we do in this extension.
    const serverInfo = loadServerDefaults();
    const serverName = serverInfo.name;
    const serverId = serverInfo.module;

    const settings: ISettings[] = await getExtensionSettings(serverId);

    // Setup logging
    const outputChannel = createOutputChannel(serverName);
    context.subscriptions.push(outputChannel, registerLogger(outputChannel));

    traceLog(`Name: ${serverName}`);
    traceLog(`Module: ${serverInfo.module}`);
    traceVerbose(`Configuration: ${JSON.stringify(serverInfo)}`);

    let isRestarting = false;
    let restartTimer: NodeJS.Timeout | undefined;
    const runServer = async () => {
        if (isRestarting) {
            if (restartTimer) {
                clearTimeout(restartTimer);
            }
            restartTimer = setTimeout(runServer, LS_SERVER_RESTART_DELAY);
            return;
        }
        isRestarting = true;
        try {
            const projectRoot = await getProjectRoot();
            const workspaceSetting = await getWorkspaceSettings(serverId, projectRoot, true);
            if (workspaceSetting.interpreter.length === 0) {
                updateStatus(vscode.l10n.t('Please select a Python interpreter.'), vscode.LanguageStatusSeverity.Error);
                traceError(
                    'Python interpreter missing:\r\n' +
                        '[Option 1] Select python interpreter using the ms-python.python (select interpreter command).\r\n' +
                        `[Option 2] Set an interpreter using "${serverId}.interpreter" setting.\r\n`,
                    `Please use Python ${PYTHON_VERSION} or greater.`,
                );
            } else {
                lsClient = await restartServer(workspaceSetting, serverId, serverName, outputChannel, lsClient);
            }
        } finally {
            isRestarting = false;
        }
    };

    context.subscriptions.push(
        onDidChangePythonInterpreter(async () => {
            await runServer();
        }),
        registerCommand(`${serverId}.showLogs`, async () => {
            outputChannel.show();
        }),
        registerCommand(`${serverId}.restart`, async () => {
            await runServer();
        }),
        onDidChangeConfiguration(async (e: vscode.ConfigurationChangeEvent) => {
            if (checkIfConfigurationChanged(e, serverId)) {
                await runServer();
            }
        }),
        registerLanguageStatusItem(serverId, serverName, `${serverId}.showLogs`),
    );

    setImmediate(async () => {
        const interpreter = getInterpreterFromSetting(serverId);
        if (interpreter === undefined || interpreter.length === 0) {
            traceLog(`Python extension loading`);
            await initializePython(context.subscriptions);
            traceLog(`Python extension loaded`);
        } else {
            await runServer();
        }
    });
}

export async function deactivate(): Promise<void> {
    if (lsClient) {
        await lsClient.stop();
    }
}
