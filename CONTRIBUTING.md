Please see [our wiki](https://github.com/microsoft/vscode-isort/wiki/Contributing-Guide) on how to contribute to this project.

## Package lockfile registry URLs

Dependabot and Microsoft developers can install through the Pylance_PublicPackages
mirror, but committed `package-lock.json` URLs should remain portable. A PR workflow
automatically replaces that mirror's tarball URLs with `https://registry.npmjs.org/`
URLs after downloading the public tarballs and verifying their existing integrity
hashes. Versions, hashes, formatting, and intentional URLs for other feeds remain
unchanged. The internal registries in `dependabot.yml` are not modified.

The workflow runs when the root `package-lock.json` changes, including in
Dependabot PRs. It only writes to PR branches in this repository, never forks.
It executes trusted base-branch code and reads the PR lockfile as data without
installing dependencies or running PR code. A concurrent push prevents the repair
commit from overwriting newer changes.

Repair commits use `GITHUB_TOKEN`. GitHub may require a maintainer to select
**Approve workflows to run** before PR validation runs on the repair commit;
token-generated pushes do not trigger `push` workflows. See
[Triggering a workflow](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
If a public tarball is unavailable or its integrity does not match, the workflow
fails without committing changes. Contributors from forks must normalize mirror
URLs locally before submitting their changes.

Run the normalizer's tests with `node --test build/normalize-package-lock.test.js`.
PR validation also sets `LOCKFILE_INTEGRATION_TEST=1` to verify a real locked
package against the public npm registry.
