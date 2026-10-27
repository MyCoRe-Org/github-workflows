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

| Input             | Required | Default                                  | Description                                                                      |
|-------------------|----------|------------------------------------------|----------------------------------------------------------------------------------|
| `node-version`    | yes      |                                          | Node.js version, e.g. `'24'`                                                     |
| `build-script`    | no       | `build`                                  | Package script to run before packing, empty to skip                              |
| `publish-command` | no       | `npm publish "$PACKAGE" --access public` | Publish command, `$PACKAGE` is the packed package, e.g. `npx jsr@0.14.3 publish` |
| `registry-url`    | no       | `https://registry.npmjs.org`             | Registry for publishing                                                          |
| `create-release`  | no       | `true`                                   | Create a GitHub release for the tag                                              |

| Secret                | Description                                               |
|-----------------------|-----------------------------------------------------------|
| `MATRIX_ACCESS_TOKEN` | Optional, see [notifications](../README.md#notifications) |

## How it works

The release runs in three jobs, so the code of the dependencies never runs with the permission to publish:

1. **build**, with read access only. A tag check stops runs on branches, [`node-setup`](../.github/actions/node-setup/action.yml)
   installs the dependencies as in [`node-build.yml`](node-build.md#how-it-works), `build-script` runs with `yarn run`
   and `yarn pack` packs the package for the next job.
2. **publish**, with `id-token: write` and `contents: write`. It installs nothing, runs `publish-command` with the
   packed package in `$PACKAGE`, and with `create-release` creates the GitHub release for the tag with the notes
   GitHub generates since the previous `v*` tag.
3. **notify** reports the result to Matrix, if configured: published, published without GitHub release, or failed.

In a single job, a compromised dependency could use `id-token: write` to publish a version of its own,
npm accepts every publish of the configured workflow. It can still change the package it is built into.

Both jobs run without cache (`cache-mode: none`), a `node_modules` restored from a poisoned cache entry would end up
in the package.

## Publishing with OIDC

Publishing uses OIDC (trusted publishing), no npm token is passed. This needs:

- `id-token: write` in the caller, as in the example.
- The package configured for trusted publishing on npmjs.com, with this repository and the file name
  of the calling workflow. npm checks the caller, not this reusable workflow, so renaming the caller requires
  changing the trusted publisher as well. The [template](../README.md#workflow-templates) names the file
  `node-release.yml`, projects that already publish with `release.yml` can keep that name.
- npm 11.5.1 or newer for the default `publish-command`, as Node.js 24 brings it. The package packed by Yarn is
  the one `yarn npm publish` would upload.

## Examples

Publish to JSR, without build script. The command runs in a checkout of the tag, with `id-token: write`,
so it names a fixed version of `jsr`:

```yaml
    with:
      node-version: '24'
      build-script: ''
      publish-command: npx jsr@0.14.3 publish
```
