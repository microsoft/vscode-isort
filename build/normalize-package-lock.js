// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

const { createHash } = require('node:crypto');

const mirrorPrefix =
    /^https:\/\/(?:devdiv\.pkgs\.visualstudio\.com\/DevDiv|pkgs\.dev\.azure\.com\/devdiv\/DevDiv)\/_packaging\/Pylance_PublicPackages\/npm\/registry\//i;

async function normalizePackageLock(source, fetchTarball = fetch) {
    const lockfile = JSON.parse(source);
    if (![2, 3].includes(lockfile.lockfileVersion) || !lockfile.packages) {
        throw new Error('Expected an npm lockfile with lockfileVersion 2 or 3 and a packages section.');
    }

    const replacements = new Map();
    const tarballs = new Map();

    async function visit(value) {
        if (!value || typeof value !== 'object') {
            return;
        }

        if (typeof value.resolved === 'string' && mirrorPrefix.test(value.resolved)) {
            const publicUrl = value.resolved.replace(mirrorPrefix, 'https://registry.npmjs.org/');
            const url = new URL(publicUrl);
            if (url.search || url.hash || !url.pathname.endsWith('.tgz')) {
                throw new Error(`Unexpected npm mirror tarball URL: ${value.resolved}`);
            }

            if (typeof value.integrity !== 'string') {
                throw new Error(`Cannot normalize ${publicUrl} without an integrity hash.`);
            }
            const hashes = value.integrity.trim().split(/\s+/);
            const algorithm = ['sha512', 'sha384', 'sha256', 'sha1'].find((name) =>
                hashes.some((hash) => hash.startsWith(`${name}-`)),
            );
            if (!algorithm) {
                throw new Error(`Unsupported integrity hash for ${publicUrl}.`);
            }

            if (!tarballs.has(publicUrl)) {
                const response = await fetchTarball(publicUrl, {
                    redirect: 'error',
                    signal: AbortSignal.timeout(30_000),
                });
                if (!response.ok) {
                    throw new Error(`Cannot fetch public npm tarball ${publicUrl}: HTTP ${response.status}.`);
                }
                tarballs.set(publicUrl, Buffer.from(await response.arrayBuffer()));
            }
            const digest = createHash(algorithm).update(tarballs.get(publicUrl)).digest('base64');
            if (!hashes.includes(`${algorithm}-${digest}`)) {
                throw new Error(`Public npm tarball integrity mismatch for ${publicUrl}.`);
            }
            replacements.set(value.resolved, publicUrl);
        }

        for (const child of Object.values(value)) {
            await visit(child);
        }
    }

    await visit(lockfile.packages);
    await visit(lockfile.dependencies);

    // Replace only resolved values, leaving formatting and all other lockfile data intact.
    return source.replace(/("resolved"\s*:\s*)("(?:\\.|[^"\\])*")/g, (match, prefix, encodedUrl) => {
        const replacement = replacements.get(JSON.parse(encodedUrl));
        return replacement ? prefix + JSON.stringify(replacement) : match;
    });
}

module.exports = { normalizePackageLock };
