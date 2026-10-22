# github-workflows

Reusable GitHub workflows and actions for MyCoRe projects.

## Workflows

| Workflow                                                  | Purpose                                                            |
|-----------------------------------------------------------|--------------------------------------------------------------------|
| [`maven-build.yml`](docs/maven-build.md)                  | Build and test a Maven project                                     |
| [`maven-deploy.yml`](docs/maven-deploy.md)                | Deploy a Maven snapshot, optionally with Docker images             |
| [`maven-release.yml`](docs/maven-release.md)              | Release with the `maven-release-plugin`, signing and rollback      |
| [`maven-version-branch.yml`](docs/maven-version-branch.md) | Create a version branch and set the next development version      |
| [`node-build.yml`](docs/node-build.md)                    | Install with Yarn and run package scripts                          |
| [`node-release.yml`](docs/node-release.md)                | Build, publish and create a GitHub release                         |
| [`forward-merge.yml`](docs/forward-merge.md)              | Open a forward-merge PR from a version branch into the next one    |
| [`dispatch-downstream.yml`](docs/dispatch-downstream.md)  | Start the snapshot deploy of dependent repositories                |
| [`snapshot-refresh.yml`](docs/snapshot-refresh.md)        | Runs in this repository, redeploys snapshots of all targets weekly |
| [`actionlint.yml`](docs/actionlint.md)                    | Runs in this repository, checks workflows and action scripts       |

Projects call a workflow with its major version and pass the secrets it needs:

```yaml
jobs:
  build:
    uses: MyCoRe-Org/github-workflows/.github/workflows/maven-build.yml@v1
    with:
      java-version: '25'
```

## Workflow templates

[`workflow-templates`](workflow-templates) holds ready-made callers for projects: pull request checks, snapshot deploy,
release, version branch and forward merge for Maven projects, CI and release for Node.js projects.
GitHub offers them under Actions, "New workflow", once they are in `workflow-templates` of the repository
[`MyCoRe-Org/.github`](https://github.com/MyCoRe-Org/.github). Copy them there after every change.

## Actions

The workflows are built from these composite actions.

| Action                                                              | Purpose                                                                           |
|---------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| [`maven-setup`](.github/actions/maven-setup/action.yml)             | Checkout, JDK with Maven cache, optional server credentials                       |
| [`node-setup`](.github/actions/node-setup/action.yml)               | Checkout, Node.js, Corepack and `yarn install`                                    |
| [`maven-pom-pin`](.github/actions/maven-pom-pin/action.yml)         | Set a version property and the scm url in a `pom.xml`, return the previous values |
| [`docker-push`](.github/actions/docker-push/action.yml)             | Build images with several tags and push them to Docker Hub                        |
| [`github-release`](.github/actions/github-release/action.yml)       | Create a GitHub release with generated notes, a notes file and assets             |
| [`workflow-dispatch`](.github/actions/workflow-dispatch/action.yml) | Dispatch workflows in other repositories, optionally wait for their results       |
| [`matrix-notify`](.github/actions/matrix-notify/action.yml)         | Send a message to a Matrix room                                                   |

## Secrets

All secrets are organization secrets of MyCoRe-Org, shared with the repositories that need them via "Selected repositories".
Callers pass them on explicitly instead of using `secrets: inherit`.

| Secret                                           | Used by                                                                     | Content                                                 |
|--------------------------------------------------|-----------------------------------------------------------------------------|---------------------------------------------------------|
| `MAVEN_USERNAME` / `MAVEN_PASSWORD`              | `maven-deploy.yml`, `maven-release.yml`                                     | Sonatype Central token for the `org.mycore` namespace   |
| `MAVEN_GPG_PRIVATE_KEY` / `MAVEN_GPG_PASSPHRASE` | `maven-release.yml`                                                         | Signing key                                             |
| `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN`         | `maven-deploy.yml`, `maven-release.yml`                                     | Docker Hub login, needed with `docker-images`           |
| `RELEASE_TOKEN`                                  | `maven-release.yml`, `maven-version-branch.yml`                             | Token that may push to the protected branch             |
| `PR_TOKEN`                                       | `forward-merge.yml`                                                         | Token creating the forward-merge PR                     |
| `DISPATCH_TOKEN`                                 | `dispatch-downstream.yml`, `snapshot-refresh.yml`                           | Token with `actions: write` on the target repositories  |
| `MATRIX_ACCESS_TOKEN`                            | `maven-release.yml`, `maven-version-branch.yml`, `node-release.yml`, `snapshot-refresh.yml` | Access token of the Matrix account sending notifications |

Every workflow of a selected repository can read these secrets, on any branch.
Share a secret only with the repositories that need it, in particular the signing key.
This repository needs `DISPATCH_TOKEN` for the [snapshot refresh](docs/snapshot-refresh.md),
the requirements for that token are described in [dispatch-downstream](docs/dispatch-downstream.md#token).

## Notifications

Releases, version branches and failures of the snapshot refresh are reported to a Matrix room:

| Workflow                   | Message                                                                     |
|----------------------------|-----------------------------------------------------------------------------|
| `maven-release.yml`        | Released, released with a failing Docker push or GitHub release, failed, rolled back |
| `maven-version-branch.yml` | Branch created or failed                                                    |
| `node-release.yml`         | Published or failed                                                         |
| `snapshot-refresh.yml`     | Failed, with the failing targets                                            |

The room is set by organization variables, which the workflows read from the calling repository:

| Variable           | Example                | Content                                    |
|--------------------|------------------------|--------------------------------------------|
| `MATRIX_HOMESERVER` | `https://matrix.org`   | Base URL of the homeserver                 |
| `MATRIX_ROOM_ID`   | `!AbCdEf:matrix.org`   | Internal id of the room, see its settings  |

A repository variable with the same name sends the messages of that repository to another room.
Without the variables or without `MATRIX_ACCESS_TOKEN`, no message is sent and nothing fails.

The messages come from a separate Matrix account, which has to be a member of the room. Its access token is shown
in Element under Settings, Help & About. The room should not be end-to-end encrypted, as the messages are sent unencrypted.

## Versioning

Workflows and actions are released together. Use a major tag (`@v1`) in callers.
Workflows reference the actions of this repository with the self-repository syntax (`uses: $/.github/actions/...`),
which resolves to the commit of the running workflow. A caller referencing a branch, a tag or a commit SHA
therefore runs the actions of exactly that state. The syntax needs runner 2.336.0 or newer.

Release a change in this order:

1. Push it to a branch and run the affected workflows from a test project referencing `@<branch>`
2. Merge it, tag the version, e.g. `v1.4.0`, and move `v1` to it

Third-party actions are pinned to commit SHAs and updated by Dependabot.

## License

[GPL-3.0](LICENSE.txt)
