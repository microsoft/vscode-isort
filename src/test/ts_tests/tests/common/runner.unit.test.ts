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

        // Stub childProcess.execFile
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

    test('Returns empty WorkspaceEdit when content is unchanged (stdout empty)', async () => {
        getWorkspaceSettingsStub.resolves(mockSettings);

        execFileStub.callsFake((runner, args, options, callback) => {
            callback(null, '', '');
        });

        const doc = createMockTextDocument('import os\nimport sys\n');
        const result = await runner.textEditRunner('isort', doc);

        assert.instanceOf(result, WorkspaceEdit);
        // Check that the WorkspaceEdit has no entries
        assert.strictEqual(result.size, 0);
    });

    test('Returns empty WorkspaceEdit when content is unchanged (stdout equals content)', async () => {
        getWorkspaceSettingsStub.resolves(mockSettings);

        const originalContent = 'import os\nimport sys\n';
        execFileStub.callsFake((runner, args, options, callback) => {
            // isort returns the same content
            callback(null, originalContent, '');
        });

        const doc = createMockTextDocument(originalContent);
        const result = await runner.textEditRunner('isort', doc);

        assert.instanceOf(result, WorkspaceEdit);
        // Check that the WorkspaceEdit has no entries
        assert.strictEqual(result.size, 0);
    });

    test('Returns WorkspaceEdit with edits when content is changed', async () => {
        getWorkspaceSettingsStub.resolves(mockSettings);

        const originalContent = 'import sys\nimport os\n';
        const sortedContent = 'import os\nimport sys\n';

        execFileStub.callsFake((runner, args, options, callback) => {
            callback(null, sortedContent, '');
        });

        const doc = createMockTextDocument(originalContent);
        const result = await runner.textEditRunner('isort', doc);

        assert.instanceOf(result, WorkspaceEdit);
        // Check that the WorkspaceEdit has entries
        assert.isTrue(result.size > 0);

        // Verify the edit contains the sorted content
        const entries = result.entries();
        assert.strictEqual(entries.length, 1);
        const [uri, edits] = entries[0];
        assert.strictEqual(uri.fsPath, doc.uri.fsPath);
        assert.strictEqual(edits.length, 1);
        assert.strictEqual(edits[0].newText, sortedContent);
    });

    test('Returns empty WorkspaceEdit when settings unavailable (no interpreter)', async () => {
        // Return undefined settings (no interpreter configured)
        getWorkspaceSettingsStub.resolves(undefined);

        const doc = createMockTextDocument('import os\nimport sys\n');
        const result = await runner.textEditRunner('isort', doc);

        assert.instanceOf(result, WorkspaceEdit);
        // Check that the WorkspaceEdit has no entries (fallback path)
        assert.strictEqual(result.size, 0);
    });

    test('Returns empty WorkspaceEdit when execFile throws error', async () => {
        getWorkspaceSettingsStub.resolves(mockSettings);

        execFileStub.callsFake((runner, args, options, callback) => {
            callback(new Error('Command failed'), '', 'Error executing isort');
        });

        const doc = createMockTextDocument('import os\nimport sys\n');
        const result = await runner.textEditRunner('isort', doc);

        assert.instanceOf(result, WorkspaceEdit);
        // Check that the WorkspaceEdit has no entries (error path)
        assert.strictEqual(result.size, 0);
    });

    test('Handles line ending conversion correctly', async () => {
        getWorkspaceSettingsStub.resolves(mockSettings);

        const originalContent = 'import sys\nimport os\n';
        const sortedContent = 'import os\nimport sys\n';

        execFileStub.callsFake((runner, args, options, callback) => {
            callback(null, sortedContent, '');
        });

        // Create document with CRLF line endings
        const doc = {
            ...createMockTextDocument(originalContent),
            eol: EndOfLine.CRLF,
        } as unknown as TextDocument;

        const result = await runner.textEditRunner('isort', doc);

        assert.instanceOf(result, WorkspaceEdit);
        assert.isTrue(result.size > 0);

        const entries = result.entries();
        const [, edits] = entries[0];
        // The content should be converted to CRLF
        assert.include(edits[0].newText, '\r\n');
    });
});
