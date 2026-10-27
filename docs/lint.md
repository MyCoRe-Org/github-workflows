# lint.yml

Checks the workflows, the workflow templates, the shell and Python code and `snapshot-targets.txt` of this repository,
and audits the workflows and actions with zizmor, on every push and pull request that changes one of them.
It runs in this repository and is not meant to be called by projects.

It can also be started by hand: Actions, "Lint", "Run workflow". That is needed after a force push, for example of
a squashed commit, as the path filters then find no changed files and the workflow does not start by itself.

## What is checked

| Step                                     | Checks                                                                                                                                                                                         |
|------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Run actionlint                           | All workflows in `.github/workflows`: syntax, expressions, references like `inputs.*` and `steps.*`, and the `run` blocks with shellcheck                                                      |
| Run actionlint on the workflow templates | The callers in `workflow-templates`, with the placeholder `$default-branch` replaced by `main`                                                                                                 |
| Run shellcheck                           | The scripts `.github/actions/*/*.sh` and the `run` blocks of all composite actions, with `${{ … }}` expressions replaced by a placeholder                                                      |
| Check the Python scripts                 | The scripts `.github/actions/*/*.py` parse as Python, without running them                                                                                                                     |
| Run zizmor                               | Security of the workflows and actions, e.g. injection, permissions, pinning and caches. Accepted findings are ignored with a `# zizmor: ignore[…]` comment where they occur, giving the reason |
| Check snapshot-targets.txt               | Every line has the form `<owner/repository> <workflow> [<branch or pattern>]` and none uses `*` alone, errors point to the line                                                                |

All steps run even if another one fails, so one run shows all problems.
Findings in the `run` blocks of composite actions name the action and the step index, their line numbers count
from the start of that `run` block.

## What is not checked

- Inputs passed to the actions of this repository. actionlint does not support the self-repository syntax `$/` yet
  ([rhysd/actionlint#711](https://github.com/rhysd/actionlint/issues/711)), its errors about `$/` references are
  ignored. Remove the `-ignore` once a release supports it.
- `cache-mode` of jobs. actionlint does not know the key yet
  ([rhysd/actionlint#745](https://github.com/rhysd/actionlint/issues/745)), its error about it is ignored.
  Remove that `-ignore` as well once a release supports it.
- The structure of the `action.yml` files.

## Updating actionlint and zizmor

The steps "Install actionlint" and "Install zizmor" download fixed releases and verify their checksums.
Dependabot does not update them. To update, set `VERSION` and `SHA256`:

- actionlint: `SHA256` is the line of `actionlint_<version>_linux_amd64.tar.gz` in `actionlint_<version>_checksums.txt`
  of the release.
- zizmor: `SHA256` is the digest of `zizmor-x86_64-unknown-linux-gnu.tar.gz` on the release page. A new version may
  bring new audits, whose findings need a fix or an ignore comment.

## Running locally

```sh
actionlint -ignore 'specifying action "\$/' -ignore 'reusable workflow call "\$/' \
  -ignore 'unexpected key "cache-mode" for "job" section'
shellcheck .github/actions/*/*.sh
for script in .github/actions/*/*.py; do
  python3 -I -c 'import ast, sys; ast.parse(open(sys.argv[1], encoding="utf-8").read(), sys.argv[1])' "$script"
done
zizmor --offline .
```

The loop of the step "Run shellcheck" also runs locally, with [yq](https://github.com/mikefarah/yq) 4 installed
and `RUNNER_TEMP` set to a temporary directory.
