# node-release-tag.yml

Releases a Node.js package by hand: sets the version in the package metadata, commits it, and pushes the commit
and the tag `v<version>` with the GitHub App. The tag starts the release workflow of the project, which publishes
the package with [`node-release.yml`](node-release.md).

## Usage

One caller handles both, the dispatch and the tag it pushes. Projects publishing with trusted publishing keep
the file name the trusted publisher on npmjs.com is configured with, see [OIDC](node-release.md#publishing-with-oidc).

```yaml
name: Release

on:
  push:
    tags:
      - 'v*.*.*'
  workflow_dispatch:
    inputs:
      version:
        description: 'Version to release (e.g. 1.2.3)'
        required: true

permissions: {}

jobs:
  tag:
    if: github.event_name == 'workflow_dispatch'
    permissions:
      contents: read
    uses: MyCoRe-Org/github-workflows/.github/workflows/node-release-tag.yml@v1
    with:
      version: ${{ inputs.version }}
    secrets:
      RELEASE_APP_PRIVATE_KEY: ${{ secrets.RELEASE_APP_PRIVATE_KEY }}
      MATRIX_ACCESS_TOKEN: ${{ secrets.MATRIX_ACCESS_TOKEN }}

  publish:
    if: github.event_name == 'push'
    permissions:
      contents: write
      id-token: write
    uses: MyCoRe-Org/github-workflows/.github/workflows/node-release.yml@v1
    with:
      node-version: '24'
    secrets:
      MATRIX_ACCESS_TOKEN: ${{ secrets.MATRIX_ACCESS_TOKEN }}
```

To release, open the workflow in the Actions tab, choose the branch to release from and enter the version without
a leading `v`. Pushing a tag by hand still works as before.

## Before the first release

- The [GitHub App](../README.md#push-access), installed on the repository, and `RELEASE_APP_CLIENT_ID`. A tag pushed
  with `GITHUB_TOKEN` starts no workflow, so the workflow fails right away without the App. On a protected branch,
  the App needs to be a bypass actor of its ruleset.
- The [environment `release`](../README.md#the-environment-release) with `RELEASE_APP_PRIVATE_KEY`, its deployment
  branches decide which branches may be released.

## Inputs

| Input          | Required | Default        | Description                                                                |
|----------------|----------|----------------|----------------------------------------------------------------------------|
| `version`      | yes      |                | Version to release, e.g. `1.2.3` or `1.2.3-beta.1`, without a leading `v`  |
| `version-file` | no       | `package.json` | JSON file holding the version, e.g. `jsr.json`, the same as `node-release` |
| `environment`  | no       | `release`      | Environment holding `RELEASE_APP_PRIVATE_KEY`                              |

| Secret                    | Description                                                                |
|---------------------------|----------------------------------------------------------------------------|
| `RELEASE_APP_PRIVATE_KEY` | Private key of the GitHub App, see [Push access](../README.md#push-access) |
| `MATRIX_ACCESS_TOKEN`     | Optional, see [notifications](../README.md#notifications)                  |

## How it works

The workflow runs a single job in the environment, it runs no code of the project:

1. [`check-trigger`](../.github/actions/check-trigger/action.yml) refuses runs on tags and runs started by the account
   of `DISPATCH_TOKEN`, a missing `RELEASE_APP_CLIENT_ID` stops the run as well.
2. The version is set in `version-file` with a short Node.js script instead of `npm version`, which would run the
   version scripts of the project. Indentation, key order and the end of the file are kept. If the file would change
   in more than the version line, e.g. as it is written on a single line, the run fails and the version has to be set
   by hand.
3. The change is committed as `chore(release): v<version>` by the account that started the run, and tagged with an
   annotated tag `v<version>`.
4. With a token of the GitHub App, created right before, the commit and the tag are pushed atomically, after
   checking that the tag does not exist. If the branch moved in the meantime, the push fails and nothing is pushed.
5. The tag starts the release workflow of the project. Failures of this workflow are reported to Matrix, if
   configured, the result of the publishing comes from `node-release.yml`.

Lock files keep no version of the package itself with Yarn, a `package-lock.json` of npm would not be updated.
