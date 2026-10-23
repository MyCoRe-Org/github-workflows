# require-permission.yml

Fails unless a user has at least a given permission on the repository. Jobs that need it only run for trusted users.
It is meant for workflows that anybody can start, e.g. by a comment on a pull request.

## Usage

```yaml
name: Snapshot on Comment

on:
  issue_comment:
    types: [created]

permissions:
  contents: read

jobs:
  permission:
    if: github.event.issue.pull_request && github.event.comment.body == '/snapshot'
    uses: MyCoRe-Org/github-workflows/.github/workflows/require-permission.yml@v1

  snapshot:
    needs: permission
    runs-on: ubuntu-latest
    steps:
      - run: echo "only reached for users with write permission"
```

Everybody can comment on a pull request of a public repository, so the job `snapshot` must not rely on the comment
alone. With `needs: permission`, it only runs if the commenting user has at least write permission.

Workflows started by `push` or by hand with `workflow_dispatch` need no check, both already require write permission.
[`maven-deploy-pr.yml`](maven-deploy-pr.md) uses it as a deliberate release of a pull request.
Pull requests from forks run without secrets.

## Inputs

| Input                 | Required | Default        | Description                                                          |
|-----------------------|----------|----------------|----------------------------------------------------------------------|
| `actor`               | no       | `github.actor` | Login of the user to check                                           |
| `required-permission` | no       | `write`        | Minimum permission: `admin`, `maintain`, `write`, `triage` or `read` |

Keep the default `actor`, the user who caused the event. Never take it from text the user can write,
like the body of a pull request or a comment.

The workflow checks the permission on the repository it runs in and needs no secrets. It reads the permission with
`GITHUB_TOKEN`, which only covers that repository.

## How it works

1. An unknown `required-permission` fails the run. A typo would otherwise rank lowest and let everybody pass.
2. The permission of the user is read from the REST API. Its field `role_name` names the role exactly. The older field
   `permission` maps `maintain` to `write` and `triage` to `read`, so a check for `maintain` or `triage` would fail
   for those very users. A custom role of the organization falls back to the permission it is based on.
3. The run fails if the role ranks below the required one, in the order `admin`, `maintain`, `write`, `triage`, `read`,
   or if the user has no access at all.
