# CFS package authentication

This action authenticates npm and pip to the `Pylance_PublicPackages` Azure Artifacts feed through GitHub Actions OIDC. It creates temporary package-manager configuration containing a short-lived Azure DevOps access token and removes it at the end of the job.

Workflows that call the setup operation must grant `id-token: write`. They must also call the cleanup operation from an `always()` step.

## Repository identity

The repository uses an immutable GitHub OIDC subject:

```text
repository_owner_id:6154722:repository_id:479474102
```

Inspect or restore the repository subject configuration:

```powershell
gh api repos/microsoft/vscode-isort/actions/oidc/customization/sub

gh api --method PUT repos/microsoft/vscode-isort/actions/oidc/customization/sub `
  -F use_default=false `
  -F 'include_claim_keys[]=repository_owner_id' `
  -F 'include_claim_keys[]=repository_id'
```

## Managed identity

The shared identity is in the Microsoft tenant and development subscription:

- Client ID: `92c669e8-02ad-4ce6-ad73-f222fc7177e2`
- Resource group: `managed_identities`
- Identity name: `PyrxCfsAccessForGitHub`
- Tenant: `72f988bf-86f1-41af-91ab-2d7cd011db47`
- Subscription: `daa135f2-0a85-4d87-bda5-7e765966cd64`

It must have at least collaborator access to the `Pylance_PublicPackages` feed. The repository credential is:

```powershell
az identity federated-credential create `
  --resource-group managed_identities `
  --identity-name PyrxCfsAccessForGitHub `
  --name VscodeIsortCfsAccessForAllWorkflows_mm `
  --issuer https://token.actions.githubusercontent.com `
  --subject repository_owner_id:6154722:repository_id:479474102 `
  --audiences api://AzureADTokenExchange
```

An `AADSTS700213` error means the emitted subject does not match a federated credential. Copy the complete subject from the failed `azure/login` step and compare it with the immutable subject above.

## Feed endpoints

- npm: `https://devdiv.pkgs.visualstudio.com/DevDiv/_packaging/Pylance_PublicPackages/npm/registry/`
- PyPI: `https://devdiv.pkgs.visualstudio.com/DevDiv/_packaging/Pylance_PublicPackages/pypi/simple/`

Do not commit a token-bearing `.npmrc`, `pip.conf`, or URL. The action writes credentials only below `${{ runner.temp }}`.

## Dependabot

Dependabot does not run this action. `.github/dependabot.yml` declares separate `npm-registry` and `python-index` entries with the same tenant and client IDs.

Dependabot runs through GitHub Actions and uses the same `https://token.actions.githubusercontent.com` issuer and
immutable repository subject as other workflows. The existing `VscodeIsortCfsAccessForAllWorkflows_mm` credential
covers Dependabot because its subject omits event context.

Dependabot reads configuration from the default branch, so verify its npm and pip jobs after the change is merged.

## Sibling repository rollout

For each sibling repository:

1. Record the immutable repository owner and repository IDs.
2. Configure the repository OIDC subject with only `repository_owner_id` and `repository_id`.
3. Add a uniquely named GitHub Actions federated credential to the shared managed identity.
4. Verify the identity's `Pylance_PublicPackages` feed role.
5. Route every GitHub Actions npm and pip install through temporary authenticated configuration.
6. Regenerate npm lockfiles and hashed Python requirements through the internal feed.
7. Add the npm and Python registries to every applicable Dependabot update block.
8. Test push and pull-request workflows in the upstream repository.
9. After merge, run Dependabot and verify the existing repository-wide credential authorizes its OIDC request.

For vscode-isort, manually dispatch `Push Validation` against the upstream feature branch and open a draft pull request to exercise both build paths before merge.
