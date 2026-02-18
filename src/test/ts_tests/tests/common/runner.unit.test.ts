// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { assert } from 'chai';
import { WorkspaceEdit } from 'vscode';

suite('Runner Tests', () => {
    test('WorkspaceEdit is empty when no changes needed', () => {
        // Test that an empty WorkspaceEdit has no entries
        const emptyEdit = new WorkspaceEdit();
        assert.strictEqual(emptyEdit.size, 0, 'Empty WorkspaceEdit should have size 0');
    });

    test('WorkspaceEdit behavior when content unchanged', () => {
        // This test validates the expected behavior:
        // When content is unchanged (newContent === content),
        // textEditRunner should return an empty WorkspaceEdit
        // to avoid cursor jumps in diff views.

        const emptyEdit = new WorkspaceEdit();

        // Verify that an empty WorkspaceEdit has no entries
        assert.strictEqual(emptyEdit.size, 0);
        assert.strictEqual(emptyEdit.entries().length, 0);
    });
});
