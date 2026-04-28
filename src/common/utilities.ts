// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

// Thin wrapper: delegates to vscode-common-python-lsp shared package.
// getDocumentSelector is kept local so tests can stub isVirtualWorkspace
// on the local vscodeapi barrel without cross-module mocking issues.
import { DocumentSelector } from 'vscode-languageclient';
import { isVirtualWorkspace } from './vscodeapi';

export { getLSClientTraceLevel, getInterpreterFromSetting, getProjectRoot } from '@vscode/common-python-lsp';

export function getDocumentSelector(): DocumentSelector {
    return isVirtualWorkspace()
        ? [{ language: 'python' }]
        : [
              { scheme: 'file', language: 'python' },
              { scheme: 'untitled', language: 'python' },
              { scheme: 'vscode-notebook', language: 'python' },
              { scheme: 'vscode-notebook-cell', language: 'python' },
          ];
}
