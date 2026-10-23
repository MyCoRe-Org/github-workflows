# maven-deploy-pr.yml

Deploys the snapshot of a pull request as `<version>-<qualifier>-SNAPSHOT`, e.g. `2026.06.1-alias-fix-SNAPSHOT`,
so a change can be tested before it is merged. Meant for projects without releases, like plugins and the
reposis applications, see [When to use it](#when-to-use-it).

## Usage

```yaml
name: Snapshot Deploy (PR)

on:
  pull_request:
    types: [labeled, synchronize, edited]

permissions:
  contents: read

jobs:
  deploy:
    concurrency:
      group: snapshot-deploy-pr-${{ github.repository }}-${{ github.event.pull_request.number }}
      cancel-in-progress: true
    # only pull requests with the label and a filled in snapshot.qualifier,
    # deploy.name is the legacy key of the pull request templates of gbv/reposis_workflows
    if: |
      contains(github.event.pull_request.labels.*.name, 'snapshot-deploy') &&
      (contains(github.event.pull_request.body, 'snapshot.qualifier:') ||
        contains(github.event.pull_request.body, 'deploy.name:')) &&
      !contains(github.event.pull_request.body, 'snapshot.qualifier: <required>') &&
      !contains(github.event.pull_request.body, 'deploy.name: <required>')
    uses: MyCoRe-Org/github-workflows/.github/workflows/maven-deploy-pr.yml@v1
    with:
      java-version: '25'
    secrets:
      MAVEN_USERNAME: ${{ secrets.MAVEN_USERNAME }}
      MAVEN_PASSWORD: ${{ secrets.MAVEN_PASSWORD }}
```

A pull request is deployed when it has the label `snapshot-deploy` and its description a line
`snapshot.qualifier: <qualifier>`. Every new commit, a changed description and every added label deploy it again.
A section for the pull request template of the project:

````markdown
<!--
## Snapshot Deployment *(optional)*

```text
snapshot.qualifier: <required>
```

Replace the placeholder to deploy the pull request as <version>-<qualifier>-SNAPSHOT.
The deployment needs the label `snapshot-deploy`.
-->
````

The legacy key `deploy.name` of the pull request templates of `gbv/reposis_workflows` is still accepted.
If a description has both, `snapshot.qualifier` is used. A caller whose `if` only checks for `deploy.name` needs
the `if` above before its pull request template switches to `snapshot.qualifier`, otherwise it deploys nothing.

## Inputs

| Input            | Required | Default                         | Description                                                                             |
|------------------|----------|---------------------------------|-----------------------------------------------------------------------------------------|
| `java-version`   | yes      |                                 | Java version, e.g. `'25'`                                                               |
| `required-label` | no       | `snapshot-deploy`               | Label the pull request needs                                                            |
| `actor`          | no       | `github.actor`                  | User whose permission is checked, see [`require-permission.yml`](require-permission.md) |
| `labels`         | no       | labels of the pull request      | Labels as comma separated list                                                          |
| `payload`        | no       | description of the pull request | Text containing the line `snapshot.qualifier: <qualifier>`                              |
| `skip-tests`     | no       | `false`                         | See [`maven-deploy.yml`](maven-deploy.md)                                               |
| `setup-browser`  | no       | `false`                         | See [`maven-build.yml`](maven-build.md)                                                 |
| `project-setup`  | no       | `false`                         | See [`maven-build.yml`](maven-build.md#project-setup)                                   |

| Secret                              | Description            |
|-------------------------------------|------------------------|
| `MAVEN_USERNAME` / `MAVEN_PASSWORD` | Sonatype Central token |

The inputs and secrets are those of `maven-deploy-from-pr.yml` of `gbv/reposis_workflows`, its callers only change `uses:`.

## How it works

1. [`require-permission.yml`](require-permission.md) checks that the user who caused the event has write permission.
2. The pull request is checked: the event must be `pull_request`, the pull request must not come from a fork,
   it needs the label, and the description a line starting with `snapshot.qualifier:`, or with the legacy
   `deploy.name:`. The qualifier may only contain letters, digits, `.`, `_` and `-`.
3. [`maven-deploy.yml`](maven-deploy.md) builds the merge result of the pull request and deploys it with the
   qualifier as `version-qualifier`: `2026.06.1-SNAPSHOT` becomes `2026.06.1-<qualifier>-SNAPSHOT`.
   The snapshot of the branch itself stays untouched. Central removes these snapshots after 90 days like all others.

## When to use it

The deploy builds the code of the pull request with the Central token. Who gets code into such a run can read the
token. That is safe here for two reasons:

- With the event `pull_request`, GitHub gives no secrets to pull requests from forks. The workflow also refuses them
  explicitly, and refuses every other event.
- Pull requests from the repository itself come from people with write permission, who can read the organization
  secrets of the repository anyway, with any workflow on a branch of their own. The deploy adds no new way to them.

So the label and the permission check are a deliberate release of a pull request, not a security boundary.
Use the workflow only in repositories where everybody with write permission is trusted with the Central token.
It does not fit repositories that keep the Central token in an environment restricted to protected branches,
as pull request runs do not get it then.

Never build the code of a pull request in a workflow started by `pull_request_target`, `workflow_run` or a comment:
those run with the secrets also for pull requests from forks, so anybody could read the token. This workflow refuses
these events, and the other workflows here only check out the commit of the event, for these events the base branch.
