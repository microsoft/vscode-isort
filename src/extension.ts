// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as vscode from 'vscode';
import {
    createToolContext,
    deactivateServer,
    loadServerDefaults,
    PythonEnvironmentsProvider,
    registerCommonSubscriptions,
    registerLogger,
    ToolExtensionContext,
    traceError,
} from '@vscode/common-python-lsp';
import { EXTENSION_ROOT_DIR, ISORT_TOOL_CONFIG } from './common/constants';
import { getServerEnabled, logLegacySettings } from './common/settings';
import { registerSortImportFeatures, unRegisterSortImportFeatures } from './common/sortImports';

let toolContext: ToolExtensionContext | undefined;
let sortFeaturesDisposable: (vscode.Disposable & { startup: () => Promise<void> }) | undefined;

function cleanupSortFeatures(): void {
    unRegisterSortImportFeatures();
    if (sortFeaturesDisposable) {
        sortFeaturesDisposable.dispose();
        sortFeaturesDisposable = undefined;
    }
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
    const serverInfo = loadServerDefaults(EXTENSION_ROOT_DIR);
    const outputChannel = vscode.window.createOutputChannel(serverInfo.name, { log: true });
    context.subscriptions.push(outputChannel, registerLogger(outputChannel));

    const pythonProvider = new PythonEnvironmentsProvider(ISORT_TOOL_CONFIG);
    context.subscriptions.push(pythonProvider);

    toolContext = createToolContext({ serverInfo, outputChannel, toolConfig: ISORT_TOOL_CONFIG, pythonProvider });
    context.subscriptions.push({ dispose: () => toolContext?.dispose() });

    // Override runServer to handle the serverEnabled toggle.
    // When disabled, stop the LSP server and switch to local code actions.
    // The sort-features registration is idempotent (calls unRegister first),
    // so rapid calls from config/interpreter changes are safe.
    const originalRunServer = toolContext.runServer.bind(toolContext);
    toolContext.runServer = async () => {
        if (!toolContext) {
            return;
        }
        if (!getServerEnabled(ISORT_TOOL_CONFIG.toolId)) {
            if (toolContext.lsClient) {
                try {
                    await toolContext.lsClient.stop();
                } catch (ex) {
                    traceError(`Server: Stop failed: ${ex}`);
                }
                toolContext.lsClient = undefined;
            }
            cleanupSortFeatures();
            sortFeaturesDisposable = registerSortImportFeatures(ISORT_TOOL_CONFIG.toolId);
            await sortFeaturesDisposable.startup();
        } else {
            cleanupSortFeatures();
            await originalRunServer();
        }
    };

    registerCommonSubscriptions(context, {
        serverInfo,
        outputChannel,
        toolConfig: ISORT_TOOL_CONFIG,
        toolContext,
        pythonProvider,
    });

    logLegacySettings();

    setImmediate(() => toolContext!.initialize(context.subscriptions));
}

export async function deactivate(): Promise<void> {
    cleanupSortFeatures();
    await deactivateServer(toolContext);
}
