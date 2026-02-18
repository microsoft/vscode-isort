// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { assert } from 'chai';
import * as childProcess from 'child_process';
import * as sinon from 'sinon';
import { EndOfLine, TextDocument, Uri, WorkspaceEdit } from 'vscode';
import * as runner from '../../../../common/runner';
import * as settings from '../../../../common/settings';

suite('textEditRunner Tests', () => {
    let sandbox: sinon.SinonSandbox;
    let getWorkspaceSettingsStub: sinon.SinonStub;
    let execFileStub: sinon.SinonStub;

    const mockSettings = {
        interpreter: ['/usr/bin/python3'],
        args: [],
        path: [],
        importStrategy: 'fromEnvironment',
        check: false,
        severity: { E: 'Error' }, // eslint-disable-line @typescript-eslint/naming-convention
        cwd: '/workspace',
    };

    setup(() => {
        sandbox = sinon.createSandbox();
        getWorkspaceSettingsStub = sandbox.stub(settings, 'getWorkspaceSettings');
        execFileStub = sandbox.stub(childProcess, 'execFile');
    });

    teardown(() => {
        sandbox.restore();
    });

    function createMockTextDocument(content: string, isDirty = false): TextDocument {
        return {
            uri: Uri.file('/workspace/test.py'),
            getText: () => content,
            eol: EndOfLine.LF,
            isDirty,
            isUntitled: false,
            languageId: 'python',
            version: 1,
            fileName: '/workspace/test.py',
        } as unknown as TextDocument;
    }

    test('Returns empty WorkspaceEdit when content is unchanged', async () => {
        // Stub settings to return valid configuration
        getWorkspaceSettingsStub.resolves(mockSettings);

        // Stub execFile to return empty stdout (simulating no changes from isort)
        execFileStub.callsFake(
            (
                _file: string,
                _args: string[],
                _options: childProcess.ExecFileOptions,
                callback: (error: Error | null, stdout: string, stderr: string) => void,
            ) => {
                callback(null, '', '');
                return {} as childProcess.ChildProcess;
            },
        );

        const content = 'import os\nimport sys\n';
        const doc = createMockTextDocument(content);
        const result = await runner.textEditRunner('isort', doc);

        // Verify that an empty WorkspaceEdit is returned when content is unchanged
        assert.instanceOf(result, WorkspaceEdit);
        assert.strictEqual(result.size, 0, 'WorkspaceEdit should be empty when content is unchanged');
        assert.strictEqual(result.entries().length, 0, 'WorkspaceEdit should have no entries');
    });

    test('Returns WorkspaceEdit with edits when content is changed', async () => {
        getWorkspaceSettingsStub.resolves(mockSettings);

        const originalContent = 'import sys\nimport os\n';
        const sortedContent = 'import os\nimport sys\n';

        // Stub execFile to return sorted content
        execFileStub.callsFake(
            (
                _file: string,
                _args: string[],
                _options: childProcess.ExecFileOptions,
                callback: (error: Error | null, stdout: string, stderr: string) => void,
            ) => {
                callback(null, sortedContent, '');
                return {} as childProcess.ChildProcess;
            },
        );

        const doc = createMockTextDocument(originalContent);
        const result = await runner.textEditRunner('isort', doc);

        // Verify that a WorkspaceEdit with entries is returned when content changes
        assert.instanceOf(result, WorkspaceEdit);
        assert.isTrue(result.size > 0, 'WorkspaceEdit should have entries when content is changed');

        const entries = result.entries();
        assert.strictEqual(entries.length, 1);
        const [uri, edits] = entries[0];
        assert.strictEqual(uri.fsPath, doc.uri.fsPath);
        assert.strictEqual(edits.length, 1);
        assert.strictEqual(edits[0].newText, sortedContent);
    });

    test('Returns empty WorkspaceEdit when settings are unavailable', async () => {
        // Return undefined settings (no interpreter configured)
        getWorkspaceSettingsStub.resolves(undefined);

        const doc = createMockTextDocument('import os\nimport sys\n');
        const result = await runner.textEditRunner('isort', doc);

        // Verify that an empty WorkspaceEdit is returned in fallback path
        assert.instanceOf(result, WorkspaceEdit);
        assert.strictEqual(result.size, 0, 'WorkspaceEdit should be empty when settings are unavailable');
    });
});
