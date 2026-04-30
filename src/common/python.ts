// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

// Thin wrapper: delegates to vscode-common-python-lsp shared package.
// Creates a PythonEnvironmentsProvider singleton and exposes the
// same function signatures as the original module.

import { Disposable, Event, EventEmitter, Uri } from 'vscode';
import { PythonExtension } from '@vscode/python-extension';
import { IInterpreterDetails, PythonEnvironmentsProvider } from '@vscode/common-python-lsp';
import { ISORT_TOOL_CONFIG } from './constants';

export type { IInterpreterDetails };

// Stable relay emitter — survives provider resets via resetCachedApis()
const _onDidChangePython = new EventEmitter<void>();
export const onDidChangePythonInterpreter: Event<void> = _onDidChangePython.event;

let _provider = new PythonEnvironmentsProvider(ISORT_TOOL_CONFIG);
let _providerSub = _provider.onDidChangeInterpreter(() => _onDidChangePython.fire());

/** Expose the provider instance for server.ts to pass to shared restartServer. */
export function getPythonProvider(): PythonEnvironmentsProvider {
    return _provider;
}

export async function initializePython(disposables: Disposable[]): Promise<void> {
    return _provider.initializePython(disposables);
}

export async function getInterpreterDetails(resource?: Uri): Promise<IInterpreterDetails> {
    return _provider.getInterpreterDetails(resource);
}

/**
 * Get debugger path — falls back to legacy Python extension API
 * when the environments API doesn't support it yet.
 */
export async function getDebuggerPath(): Promise<string | undefined> {
    const result = await _provider.getDebuggerPath();
    if (result) {
        return result;
    }
    // Environments API doesn't expose debugger yet — try legacy directly
    try {
        const legacyApi = await PythonExtension.api();
        return legacyApi?.debug?.getDebuggerPackagePath();
    } catch {
        return undefined;
    }
}

/**
 * Reset cached provider for testing. The relay emitter (_onDidChangePython)
 * is module-level and survives resets. A new provider subscription is
 * immediately created so interpreter-change events keep flowing.
 * Note: callers should re-invoke initializePython() on the new provider
 * if environment-change listeners are needed.
 */
export function resetCachedApis(): void {
    _providerSub.dispose();
    _provider.dispose();
    _provider = new PythonEnvironmentsProvider(ISORT_TOOL_CONFIG);
    _providerSub = _provider.onDidChangeInterpreter(() => _onDidChangePython.fire());
}
