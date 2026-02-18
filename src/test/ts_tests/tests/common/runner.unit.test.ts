// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { assert } from 'chai';
import * as sinon from 'sinon';
import { EndOfLine, TextDocument, Uri, WorkspaceEdit, WorkspaceFolder } from 'vscode';
import * as runner from '../../../../common/runner';
import * as settings from '../../../../common/settings';
import * as utilities from '../../../../common/utilities';
import * as vscodeapi from '../../../../common/vscodeapi';

suite('textEditRunner Tests', () => {
    let sandbox: sinon.SinonSandbox;
    let getWorkspaceSettingsStub: sinon.SinonStub;
    let getWorkspaceFolderStub: sinon.SinonStub;
    let getProjectRootStub: sinon.SinonStub;
    let runScriptStub: sinon.SinonStub;

    const mockWorkspaceFolder: WorkspaceFolder = {
        uri: Uri.file('/workspace'),
        name: 'workspace',
        index: 0,
    };

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
        getWorkspaceFolderStub = sandbox.stub(vscodeapi, 'getWorkspaceFolder');
        getProjectRootStub = sandbox.stub(utilities, 'getProjectRoot');
        runScriptStub = sandbox.stub(runner, 'runScript');

        // Default stubs for workspace folder
        getWorkspaceFolderStub.returns(mockWorkspaceFolder);
        getProjectRootStub.resolves(mockWorkspaceFolder);
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
        runScriptStub.resolves({ stdout: '', stderr: '' });

        const content = 'import os\nimport sys\n';
        const doc = createMockTextDocument(content);
        const result = await runner.textEditRunner('isort', doc);

        assert.instanceOf(result, WorkspaceEdit);
        assert.strictEqual(result.size, 0, 'WorkspaceEdit should be empty when content is unchanged');
    });

    test('Returns empty WorkspaceEdit when content is unchanged (stdout equals content)', async () => {
        getWorkspaceSettingsStub.resolves(mockSettings);
        const content = 'import os\nimport sys\n';
        runScriptStub.resolves({ stdout: content, stderr: '' });

        const doc = createMockTextDocument(content);
        const result = await runner.textEditRunner('isort', doc);

        assert.instanceOf(result, WorkspaceEdit);
        assert.strictEqual(result.size, 0, 'WorkspaceEdit should be empty when content is unchanged');
    });

    test('Returns WorkspaceEdit with edits when content is changed', async () => {
        getWorkspaceSettingsStub.resolves(mockSettings);
        const originalContent = 'import sys\nimport os\n';
        const sortedContent = 'import os\nimport sys\n';
        runScriptStub.resolves({ stdout: sortedContent, stderr: '' });

        const doc = createMockTextDocument(originalContent);
        const result = await runner.textEditRunner('isort', doc);

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
        getWorkspaceSettingsStub.resolves({ ...mockSettings, interpreter: [] });

        const doc = createMockTextDocument('import os\nimport sys\n');
        const result = await runner.textEditRunner('isort', doc);

        assert.instanceOf(result, WorkspaceEdit);
        assert.strictEqual(result.size, 0, 'WorkspaceEdit should be empty when settings are unavailable');
    });

    test('Returns empty WorkspaceEdit when runScript throws error', async () => {
        getWorkspaceSettingsStub.resolves(mockSettings);
        runScriptStub.rejects(new Error('Command failed'));

        const doc = createMockTextDocument('import os\nimport sys\n');
        const result = await runner.textEditRunner('isort', doc);

        assert.instanceOf(result, WorkspaceEdit);
        assert.strictEqual(result.size, 0, 'WorkspaceEdit should be empty when runScript throws error');
    });
});
