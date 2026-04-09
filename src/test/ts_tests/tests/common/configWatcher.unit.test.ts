// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { assert } from 'chai';
import * as sinon from 'sinon';
import { Disposable, FileSystemWatcher, workspace } from 'vscode';
import { createConfigFileWatchers } from '../../../../common/configWatcher';
import { ISORT_CONFIG_FILES } from '../../../../common/constants';

interface MockFileSystemWatcher {
    watcher: FileSystemWatcher;
    rawWatcher: {
        onDidChange: sinon.SinonStub;
        onDidCreate: sinon.SinonStub;
        onDidDelete: sinon.SinonStub;
        dispose: sinon.SinonStub;
    };
    changeDisposable: { dispose: sinon.SinonStub };
    createDisposable: { dispose: sinon.SinonStub };
    deleteDisposable: { dispose: sinon.SinonStub };
    fireDidCreate(): Promise<void>;
    fireDidChange(): Promise<void>;
    fireDidDelete(): Promise<void>;
}

function createMockFileSystemWatcher(sandbox: sinon.SinonSandbox): MockFileSystemWatcher {
    let onDidChangeHandler: (() => Promise<void>) | undefined;
    let onDidCreateHandler: (() => Promise<void>) | undefined;
    let onDidDeleteHandler: (() => Promise<void>) | undefined;

    const changeDisposable = { dispose: sandbox.stub() };
    const createDisposable = { dispose: sandbox.stub() };
    const deleteDisposable = { dispose: sandbox.stub() };

    const rawWatcher = {
        onDidChange: sandbox.stub().callsFake((handler: () => Promise<void>): Disposable => {
            onDidChangeHandler = handler;
            return changeDisposable;
        }),
        onDidCreate: sandbox.stub().callsFake((handler: () => Promise<void>): Disposable => {
            onDidCreateHandler = handler;
            return createDisposable;
        }),
        onDidDelete: sandbox.stub().callsFake((handler: () => Promise<void>): Disposable => {
            onDidDeleteHandler = handler;
            return deleteDisposable;
        }),
        dispose: sandbox.stub(),
    };

    return {
        watcher: rawWatcher as unknown as FileSystemWatcher,
        rawWatcher,
        changeDisposable,
        createDisposable,
        deleteDisposable,
        fireDidCreate: async () => {
            if (onDidCreateHandler) {
                await onDidCreateHandler();
            }
        },
        fireDidChange: async () => {
            if (onDidChangeHandler) {
                await onDidChangeHandler();
            }
        },
        fireDidDelete: async () => {
            if (onDidDeleteHandler) {
                await onDidDeleteHandler();
            }
        },
    };
}

suite('Config File Watcher Tests', () => {
    let sandbox: sinon.SinonSandbox;
    let createFileSystemWatcherStub: sinon.SinonStub;
    let mockWatchers: MockFileSystemWatcher[];
    let mockWatcher: MockFileSystemWatcher['rawWatcher'];
    let changeDisposable: { dispose: sinon.SinonStub };
    let createDisposable: { dispose: sinon.SinonStub };
    let deleteDisposable: { dispose: sinon.SinonStub };
    let onConfigChangedCallback: sinon.SinonStub;

    setup(() => {
        sandbox = sinon.createSandbox();
        mockWatchers = ISORT_CONFIG_FILES.map(() => createMockFileSystemWatcher(sandbox));
        mockWatcher = mockWatchers[0].rawWatcher;
        changeDisposable = mockWatchers[0].changeDisposable;
        createDisposable = mockWatchers[0].createDisposable;
        deleteDisposable = mockWatchers[0].deleteDisposable;
        onConfigChangedCallback = sandbox.stub().resolves();

        let watcherIndex = 0;
        createFileSystemWatcherStub = sandbox.stub(workspace, 'createFileSystemWatcher').callsFake(() => {
            return mockWatchers[watcherIndex++].watcher;
        });
    });

    teardown(() => {
        sandbox.restore();
    });

    test('Creates a file watcher for each isort config file pattern', () => {
        const onConfigChanged = sandbox.stub().resolves();
        createConfigFileWatchers(onConfigChanged);

        assert.strictEqual(createFileSystemWatcherStub.callCount, ISORT_CONFIG_FILES.length);
        for (let i = 0; i < ISORT_CONFIG_FILES.length; i++) {
            assert.isTrue(
                createFileSystemWatcherStub.getCall(i).calledWith(`**/${ISORT_CONFIG_FILES[i]}`),
                `Expected watcher for pattern **/${ISORT_CONFIG_FILES[i]}`,
            );
        }
    });

    test('Server restarts when a config file is created', async () => {
        const onConfigChanged = sandbox.stub().resolves();
        createConfigFileWatchers(onConfigChanged);

        // Simulate creating a .isort.cfg file
        await mockWatchers[0].fireDidCreate();

        assert.isTrue(onConfigChanged.calledOnce, 'Expected onConfigChanged to be called when config file is created');
    });

    test('Server restarts when a config file is changed', async () => {
        const onConfigChanged = sandbox.stub().resolves();
        createConfigFileWatchers(onConfigChanged);

        // Simulate modifying pyproject.toml
        await mockWatchers[1].fireDidChange();

        assert.isTrue(onConfigChanged.calledOnce, 'Expected onConfigChanged to be called when config file is changed');
    });

    test('Server restarts when a config file is deleted', async () => {
        const onConfigChanged = sandbox.stub().resolves();
        createConfigFileWatchers(onConfigChanged);

        // Simulate deleting setup.cfg
        await mockWatchers[2].fireDidDelete();

        assert.isTrue(onConfigChanged.calledOnce, 'Expected onConfigChanged to be called when config file is deleted');
    });

    test('Server restarts for each config file type on create', async () => {
        const onConfigChanged = sandbox.stub().resolves();
        createConfigFileWatchers(onConfigChanged);

        // Fire onDidCreate for every config file pattern
        for (const mock of mockWatchers) {
            await mock.fireDidCreate();
        }

        assert.strictEqual(
            onConfigChanged.callCount,
            ISORT_CONFIG_FILES.length,
            `Expected onConfigChanged to be called once for each of the ${ISORT_CONFIG_FILES.length} config file patterns`,
        );
    });

    test('Returns a disposable for each watcher', () => {
        const onConfigChanged = sandbox.stub().resolves();
        const disposables = createConfigFileWatchers(onConfigChanged);

        assert.strictEqual(disposables.length, ISORT_CONFIG_FILES.length);
        for (const d of disposables) {
            assert.isFunction(d.dispose);
        }
    });

    test('Should dispose all subscriptions and watcher on dispose', () => {
        const watchers = createConfigFileWatchers(onConfigChangedCallback);

        watchers[0].dispose();

        assert.strictEqual(changeDisposable.dispose.callCount, 1, 'Change subscription should be disposed');
        assert.strictEqual(createDisposable.dispose.callCount, 1, 'Create subscription should be disposed');
        assert.strictEqual(deleteDisposable.dispose.callCount, 1, 'Delete subscription should be disposed');
        assert.strictEqual(mockWatcher.dispose.callCount, 1, 'Watcher should be disposed');
    });

    test('Should not call callback after dispose', () => {
        const watchers = createConfigFileWatchers(onConfigChangedCallback);

        // Dispose the watcher
        watchers[0].dispose();

        // Get the handlers and call them after disposal
        const changeHandler = mockWatcher.onDidChange.getCall(0).args[0];
        changeHandler();

        assert.strictEqual(onConfigChangedCallback.callCount, 0, 'Callback should not be called after dispose');
    });
});
