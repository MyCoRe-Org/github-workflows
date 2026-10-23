# lint.yml

Checks the workflows, the workflow templates, the shell code and `snapshot-targets.txt` of this repository on every
push and pull request that changes one of them.
It runs in this repository and is not meant to be called by projects.

It can also be started by hand: Actions, "Lint", "Run workflow". That is needed after a force push, for example of
a squashed commit, as the path filters then find no changed files and the workflow does not start by itself.

## What is checked

| Step                                     | Checks                                                                                                                                    |
|------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------|
| Run actionlint                           | All workflows in `.github/workflows`: syntax, expressions, references like `inputs.*` and `steps.*`, and the `run` blocks with shellcheck |
| Run actionlint on the workflow templates | The callers in `workflow-templates`, with the placeholder `$default-branch` replaced by `main`                                            |
| Run shellcheck                           | The scripts `.github/actions/*/*.sh` and the `run` blocks of all composite actions, with `${{ … }}` expressions replaced by a placeholder |
| Check snapshot-targets.txt               | Every line has the form `<owner/repository> <workflow> [<branch or pattern>]` and none uses `*` alone, errors point to the line           |

All steps run even if another one fails, so one run shows all problems.
Findings in the `run` blocks of composite actions name the action and the step index, their line numbers count
from the start of that `run` block.

## What is not checked

- Inputs passed to the actions of this repository. actionlint does not support the self-repository syntax `$/` yet
  ([rhysd/actionlint#711](https://github.com/rhysd/actionlint/issues/711)), its errors about `$/` references are
  ignored. Remove the `-ignore` once a release supports it.
- The structure of the `action.yml` files.

## Updating actionlint

The step "Install actionlint" downloads a fixed release and verifies its checksum. To update, set `VERSION` and
take `SHA256` from the line of `actionlint_<version>_linux_amd64.tar.gz` in `actionlint_<version>_checksums.txt`
of the release. Dependabot does not update it.

## Running locally

```sh
actionlint -ignore 'specifying action "\$/' -ignore 'reusable workflow call "\$/'
shellcheck .github/actions/*/*.sh
```

The loop of the step "Run shellcheck" also runs locally, with [yq](https://github.com/mikefarah/yq) 4 installed
and `RUNNER_TEMP` set to a temporary directory.
