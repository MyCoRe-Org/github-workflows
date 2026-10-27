# node-build.yml

Installs the dependencies of a Node.js project with Yarn and runs package scripts, e.g. lint and build.

## Usage

```yaml
name: CI

on: [ push, pull_request ]

permissions:
  contents: read

jobs:
  build:
    uses: MyCoRe-Org/github-workflows/.github/workflows/node-build.yml@v1
    with:
      node-version: '24'
```

## Inputs

| Input          | Required | Default      | Description                            |
|----------------|----------|--------------|----------------------------------------|
| `node-version` | yes      |              | Node.js version, e.g. `'24'`           |
| `scripts`      | no       | `lint build` | Space-separated package scripts to run |

The workflow needs no secrets.

## How it works

1. [`node-setup`](../.github/actions/node-setup/action.yml) checks out the repository without keeping the token
   and sets up Node.js.
2. Corepack is enabled, so the Yarn version from the `packageManager` field of `package.json` is used.
   Node.js 25 and newer no longer ship Corepack, a pinned version is installed with npm then.
3. `node_modules` is restored from the cache, keyed by runner OS and architecture, Node.js version and `yarn.lock`.
   Projects with Yarn Plug'n'Play have no `node_modules`, the cache stays empty for them.
4. `yarn install` runs with a frozen lockfile, `--frozen-lockfile` for Yarn 1 and `--immutable` for newer versions.
   A `yarn.lock` that does not match `package.json` fails the build.
5. Every script in `scripts` runs with `yarn run`, in a log group of its own.

## Examples

A project without a `build` script:

```yaml
    with:
      node-version: '24'
      scripts: lint test-publish
```
