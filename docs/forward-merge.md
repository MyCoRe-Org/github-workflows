# forward-merge.yml

Opens a pull request that merges a version branch into the next newer one, after every push to the version branch.
A fix on `2025.12.x` is offered to `2026.06.x`, from there to `main`, so it reaches all newer versions step by step.

## Usage

```yaml
name: Forward Merge

on:
  push:
    branches:
      - '[0-9][0-9][0-9][0-9].[0-9][0-9].x'

permissions:
  contents: read
  pull-requests: write

jobs:
  forward-merge:
    uses: MyCoRe-Org/github-workflows/.github/workflows/forward-merge.yml@v1
    secrets:
      PR_TOKEN: ${{ secrets.PR_TOKEN }}
```

## Inputs

| Input                  | Required | Default                   | Description                                         |
|------------------------|----------|---------------------------|-----------------------------------------------------|
| `version-branch-regex` | no       | `^[0-9]{4}\.[0-9]{2}\.x$` | Regex matching version branches                     |
| `default-target`       | no       | `main`                    | Target when the source is the newest version branch |

| Secret     | Description                                                                                        |
|------------|----------------------------------------------------------------------------------------------------|
| `PR_TOKEN` | Optional, token used to create the PR. PRs created with `GITHUB_TOKEN` do not trigger PR workflows |

Without `PR_TOKEN`, the repository setting "Allow GitHub Actions to create and approve pull requests" must be enabled,
and the checks of the pull request do not run.

## How it works

1. All branches matching `version-branch-regex` are sorted by version. The target is the next newer one,
   the newest version branch goes to `default-target`.

   | Pushed branch | Target      |
   |---------------|-------------|
   | `2024.06.x`   | `2025.06.x` |
   | `2025.06.x`   | `2025.12.x` |
   | `2025.12.x`   | `2026.06.x` |
   | `2026.06.x`   | `main`      |

   A pushed branch that does not match the regex fails the run, the trigger of the caller is wrong then.
2. If the target already contains all commits of the source, nothing happens.
3. Otherwise a pull request "Merge branch '&lt;source&gt;' into &lt;target&gt;" lists up to 100 missing commits.
   An open pull request from the same source to the same target is updated instead of opening another one.
   Pull requests from forks are never taken for it, even if their branch has the name of the source.
4. A new pull request gets a comment with the commands to resolve conflicts locally.
5. Open forward merges of the source into another branch are closed with a link to the current one. That happens
   after a [new version branch](maven-version-branch.md): with `2026.06.x` created, the next push to `2025.12.x`
   opens a pull request into `2026.06.x` and closes the one into `main`, which would skip `2026.06.x`.
   Only pull requests of the repository with the title of this workflow are closed, others stay open.

## Merging

Merge these pull requests with a merge commit, not with squash or rebase. Otherwise the commits of the source
do not become part of the history of the target, and the next forward merge lists them again.

After a release the branches differ in their versions in the poms, so the pull request conflicts there.
Resolve it locally as described in the comment and keep the versions of the target.

## Other branch names

For version branches like `1.3.x`:

```yaml
    with:
      version-branch-regex: '^[0-9]+\.[0-9]+\.x$'
```

Adjust the `branches` filter of the caller accordingly.
