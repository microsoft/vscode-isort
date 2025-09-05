// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { expect } from 'chai';

suite('Node.js Version Tests', () => {
    test('Should be running Node.js 22.x', () => {
        const nodeVersion = process.version;
        const majorVersion = parseInt(nodeVersion.split('.')[0].substring(1), 10);
        
        expect(majorVersion).to.be.at.least(22, `Expected Node.js 22.x or higher, but got ${nodeVersion}`);
    });

    test('Should have process.versions.node defined', () => {
        expect(process.versions.node).to.be.a('string');
        expect(process.versions.node.length).to.be.greaterThan(0);
    });
});