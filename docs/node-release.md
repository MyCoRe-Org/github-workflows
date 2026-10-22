# node-release.yml

Builds a Node.js package, publishes it and creates a GitHub release, when a version tag is pushed.

## Usage

```yaml
name: Release

on:
  push:
    tags:
      - 'v*.*.*'

permissions:
  contents: write
  id-token: write

jobs:
  publish:
    uses: MyCoRe-Org/github-workflows/.github/workflows/node-release.yml@v1
    with:
      node-version: '24'
    secrets:
      MATRIX_ACCESS_TOKEN: ${{ secrets.MATRIX_ACCESS_TOKEN }}
```

The workflow must run on a tag, it fails on branches to avoid a release named after the branch.
The published version comes from the package metadata, e.g. `package.json`, not from the tag,
so set both to the same version before tagging.

## Inputs

| Input             | Required | Default                            | Description                                            |
|-------------------|----------|------------------------------------|--------------------------------------------------------|
| `node-version`    | yes      |                                    | Node.js version, e.g. `'24'`                           |
| `build-script`    | no       | `build`                            | Package script to run before publishing, empty to skip |
| `publish-command` | no       | `yarn npm publish --access public` | Publish command, e.g. `npx jsr publish`                |
| `registry-url`    | no       | `https://registry.npmjs.org`       | Registry for publishing                                |
| `create-release`  | no       | `true`                             | Create a GitHub release for the tag                    |

| Secret                | Description                                                  |
|-----------------------|--------------------------------------------------------------|
| `MATRIX_ACCESS_TOKEN` | Optional, see [notifications](../README.md#notifications)   |

## How it works

1. A tag check stops runs on branches.
2. [`node-setup`](../.github/actions/node-setup/action.yml) installs the dependencies as in
   [`node-build.yml`](node-build.md#how-it-works) and configures `registry-url` for npm.
3. `build-script` runs with `yarn run`.
4. `publish-command` publishes the package.
5. With `create-release`, the GitHub release for the tag gets the notes GitHub generates since the previous `v*` tag.
6. A message reports the result to Matrix, if configured.

## Publishing with OIDC

Publishing uses OIDC (trusted publishing), no npm token is passed. This needs:

- `id-token: write` in the caller, as in the example.
- The package configured for trusted publishing on npmjs.com, with this repository and the file name
  of the calling workflow. npm checks the caller, not this reusable workflow, so renaming the caller requires
  changing the trusted publisher as well. The [template](../README.md#workflow-templates) names the file
  `node-release.yml`, projects that already publish with `release.yml` can keep that name.
- A Yarn version that supports trusted publishing. The Vue projects publish this way with Yarn 4.12.

## Examples

Publish to JSR, without build script:

```yaml
    with:
      node-version: '24'
      build-script: ''
      publish-command: npx jsr publish
```
