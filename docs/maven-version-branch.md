# maven-version-branch.yml

Creates a version branch like `2026.12.x` with the `release:branch` goal of the `maven-release-plugin`, and moves the
branch it starts from, usually `main`, to the next development version. A maintainer starts it by hand.

## Usage

```yaml
name: Maven Version Branch

on:
  workflow_dispatch:
    inputs:
      branch:
        description: 'Version branch to create from the chosen branch (e.g. 2026.12.x)'
        required: true
      developmentVersion:
        description: 'Version of the chosen branch afterwards (e.g. 2027.06.0-SNAPSHOT)'
        required: true
      mycoreDevelopmentVersion:
        description: 'MyCoRe version of the chosen branch afterwards (e.g. 2027.06.0-SNAPSHOT), empty to keep it'
        required: false

permissions:
  contents: write

jobs:
  branch:
    uses: MyCoRe-Org/github-workflows/.github/workflows/maven-version-branch.yml@v1
    with:
      java-version: '25'
      branch: ${{ inputs.branch }}
      development-version: ${{ inputs.developmentVersion }}
      dependency-development-version: ${{ inputs.mycoreDevelopmentVersion }}
    secrets:
      RELEASE_TOKEN: ${{ secrets.RELEASE_TOKEN }}
      MATRIX_ACCESS_TOKEN: ${{ secrets.MATRIX_ACCESS_TOKEN }}
```

To create a branch, open the workflow in the Actions tab, choose the branch to start from and fill in the versions.
`mycore` itself sets `dependency-property: ''`.

## Inputs

| Input                            | Required | Default          | Description                                                                       |
|----------------------------------|----------|------------------|-----------------------------------------------------------------------------------|
| `java-version`                   | yes      |                  | Java version, e.g. `'25'`                                                         |
| `branch`                         | yes      |                  | Name of the new branch, e.g. `2026.12.x`                                          |
| `development-version`            | yes      |                  | Version of the starting branch afterwards, e.g. `2027.06.0-SNAPSHOT`             |
| `dependency-property`            | no       | `mycore.version` | Property set on the starting branch, empty to skip (e.g. for `mycore` itself)     |
| `dependency-development-version` | no       |                  | Value of the property on the starting branch afterwards, empty to keep it        |
| `environment`                    | no       | `release`        | Environment of the job                                                            |

| Secret                | Description                                                                                  |
|-----------------------|----------------------------------------------------------------------------------------------|
| `RELEASE_TOKEN`       | Optional, token that may push to the protected branch, see [`maven-release.yml`](maven-release.md#tokens) |
| `MATRIX_ACCESS_TOKEN` | Optional, see [notifications](../README.md#notifications)                                   |

## How it works

1. **Check the inputs.** The branch name must be valid and must not exist yet, the development version must end
   with `-SNAPSHOT`, and no value may contain whitespace.
2. **`release:branch`** commits "[maven-release-plugin] prepare branch &lt;branch&gt;", which sets the `<tag>`
   in `<scm>` to the branch name, and creates the branch on that commit. It then sets the development version on the
   starting branch, restores the `<tag>` and commits "[maven-release-plugin] prepare for next development iteration".
   The new branch keeps the versions it had.
3. **Dependency version.** With `dependency-development-version`, the property `dependency-property` gets that value
   on the starting branch. The change is folded into the development commit.
4. **Push.** The starting branch and the new branch are pushed in one atomic push. If someone pushed to the starting
   branch in the meantime, nothing is pushed and the run fails.
5. **Notification** to Matrix, if configured.

For `mir` at `2026.06.0-SNAPSHOT`, with `branch: 2026.06.x`, `development-version: 2026.12.0-SNAPSHOT` and
`dependency-development-version: 2026.12.0-SNAPSHOT`:

| Branch      | Project version      | `mycore.version`     | `<scm><tag>` |
|-------------|----------------------|----------------------|--------------|
| `2026.06.x` | `2026.06.0-SNAPSHOT` | `2026.06.0-SNAPSHOT` | `2026.06.x`  |
| `main`      | `2026.12.0-SNAPSHOT` | `2026.12.0-SNAPSHOT` | `HEAD`       |

## After the run

- The branch commit is part of `main`, so the [forward merge](forward-merge.md) of the new branch finds nothing to merge.
- Pushed with `RELEASE_TOKEN`, the push starts the snapshot deploy of both branches. With `GITHUB_TOKEN` it starts
  no workflows.
- With a pattern in [`snapshot-targets.txt`](snapshot-refresh.md#targets), the new branch is part of the weekly
  snapshot refresh right away, as it contains the deploy workflow of `main`.
- The workflow files of the new branch are those of `main`. A different Java version for the branch is set in its
  own copies of the callers.
