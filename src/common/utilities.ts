// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

// getDocumentSelector is kept local so tests can stub isVirtualWorkspace
// on the local vscodeapi barrel without cross-module mocking issues.
// getProjectRoot is re-exported so tests can stub it via this local barrel
// (ES module exports from npm packages are not stubbable with sinon).
import { DocumentSelector } from 'vscode-languageclient';
import { isVirtualWorkspace } from './vscodeapi';

export { getProjectRoot } from '@vscode/common-python-lsp';

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
