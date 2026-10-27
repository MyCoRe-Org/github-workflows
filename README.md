# github-workflows

Reusable GitHub workflows and actions for MyCoRe projects.

## Workflows

| Workflow                                                   | Purpose                                                            |
|------------------------------------------------------------|--------------------------------------------------------------------|
| [`maven-build.yml`](docs/maven-build.md)                   | Build and test a Maven project                                     |
| [`maven-deploy.yml`](docs/maven-deploy.md)                 | Deploy a Maven snapshot, optionally with Docker images             |
| [`maven-deploy-pr.yml`](docs/maven-deploy-pr.md)           | Deploy a labeled pull request as a snapshot of its own             |
| [`maven-release.yml`](docs/maven-release.md)               | Release with the `maven-release-plugin`, signing and rollback      |
| [`maven-version-branch.yml`](docs/maven-version-branch.md) | Create a version branch and set the next development version       |
| [`node-build.yml`](docs/node-build.md)                     | Install with Yarn and run package scripts                          |
| [`node-release.yml`](docs/node-release.md)                 | Build, publish and create a GitHub release                         |
| [`forward-merge.yml`](docs/forward-merge.md)               | Open a forward-merge PR from a version branch into the next one    |
| [`dispatch-downstream.yml`](docs/dispatch-downstream.md)   | Start the snapshot deploy of dependent repositories                |
| [`require-permission.yml`](docs/require-permission.md)     | Fail unless the triggering user has a minimum permission           |
| [`snapshot-refresh.yml`](docs/snapshot-refresh.md)         | Runs in this repository, redeploys snapshots of all targets weekly |
| [`lint.yml`](docs/lint.md)                                 | Runs in this repository, checks workflows, templates and scripts   |

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
snapshot deploy of pull requests, release, version branch and forward merge for Maven projects, CI and release for
Node.js projects.
GitHub offers them under Actions, "New workflow", once they are in `workflow-templates` of the repository
[`MyCoRe-Org/.github`](https://github.com/MyCoRe-Org/.github). They stay here, as they call `@v1` and have to match
the workflows of the released version, and are copied there whenever `v1` moves, see [Versioning](#versioning).

## Actions

The workflows are built from these composite actions.

| Action                                                              | Purpose                                                                               |
|---------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| [`maven-setup`](.github/actions/maven-setup/action.yml)             | Checkout, JDK with Maven cache, without any credentials                               |
| [`node-setup`](.github/actions/node-setup/action.yml)               | Checkout, Node.js, Corepack and `yarn install`                                        |
| [`maven-pom-pin`](.github/actions/maven-pom-pin/action.yml)         | Set a version property and the scm url in a `pom.xml`, return the previous values     |
| [`docker-build`](.github/actions/docker-build/action.yml)           | Build images without credentials and save them to an archive                          |
| [`docker-push`](.github/actions/docker-push/action.yml)             | Load the images of `docker-build`, tag them and push them to Docker Hub               |
| [`github-release`](.github/actions/github-release/action.yml)       | Create a GitHub release with generated notes, a notes file and assets                 |
| [`workflow-dispatch`](.github/actions/workflow-dispatch/action.yml) | Dispatch workflows in other repositories, optionally wait for their results           |
| [`matrix-notify`](.github/actions/matrix-notify/action.yml)         | Send a message to a Matrix room                                                       |
| [`check-trigger`](.github/actions/check-trigger/action.yml)         | Fail unless the run is on a branch and not started by the account of `DISPATCH_TOKEN` |
| [`pom-diff-check`](.github/actions/pom-diff-check/action.yml)       | Fail unless a commit changes nothing but given values in `pom.xml` files              |
| [`central-publish`](.github/actions/central-publish/action.yml)     | Check and sign a bundle for Central, upload it and wait for its validation            |
| [`snapshot-upload`](.github/actions/snapshot-upload/action.yml)     | Check the snapshots of a build against the poms of the project, upload them           |

## Secrets

Callers pass every secret on by name instead of using `secrets: inherit`. Where a secret is stored decides who can
read it:

- Organization and repository secrets reach every workflow of the repository, on any branch. Everybody who can push
  a branch can read them with a workflow of their own, so write permission on a repository means access to them.
- Environment secrets only reach jobs that run in the environment, and its deployment branches decide which branches
  may do that. The caller passes them on by name all the same, the job in the environment gets their values.

Pull requests from forks get no secrets, except in workflows started by `pull_request_target`, which must therefore
never build their code.

| Secret                                           | Used by                                                                                     | Content                                                                    |
|--------------------------------------------------|---------------------------------------------------------------------------------------------|----------------------------------------------------------------------------|
| `MAVEN_USERNAME` / `MAVEN_PASSWORD`              | `maven-deploy.yml`, `maven-deploy-pr.yml`, `maven-release.yml`                              | Sonatype Central token for the `org.mycore` namespace                      |
| `MAVEN_GPG_PRIVATE_KEY` / `MAVEN_GPG_PASSPHRASE` | `maven-release.yml`                                                                         | Signing key                                                                |
| `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN`         | `maven-deploy.yml`, `maven-release.yml`                                                     | Docker Hub login, needed with `docker-images`                              |
| `RELEASE_APP_PRIVATE_KEY`                        | `maven-release.yml`, `maven-version-branch.yml`                                             | Private key of the GitHub App that pushes, see [Push access](#push-access) |
| `PR_TOKEN`                                       | `forward-merge.yml`                                                                         | Token creating the forward-merge PR                                        |
| `DISPATCH_TOKEN`                                 | `dispatch-downstream.yml`, `snapshot-refresh.yml`                                           | Token with `actions: write` on the target repositories                     |
| `MATRIX_ACCESS_TOKEN`                            | `maven-release.yml`, `maven-version-branch.yml`, `node-release.yml`, `snapshot-refresh.yml` | Access token of the Matrix account sending notifications                   |

The secrets of releases are secrets of the [environment `release`](#the-environment-release) in each repository that
releases: the Central token, the signing key, the key of the GitHub App and, with release images, the Docker Hub login.
The others are organization secrets of MyCoRe-Org, shared with the repositories that need them via
"Selected repositories".

An environment secret is only out of reach if no organization secret holds the same token. Snapshot deploys need the
Central token and the Docker Hub login as well: give them tokens of their own, or keep them in an environment too,
see [`maven-deploy.yml`](docs/maven-deploy.md#environment). As long as Central offers no token limited to snapshots,
a token for snapshots can publish releases as well, so share it only with repositories whose writers are trusted
with that.

This repository needs `DISPATCH_TOKEN` for the [snapshot refresh](docs/snapshot-refresh.md),
the requirements for that token are described in [dispatch-downstream](docs/dispatch-downstream.md#token).

### The environment `release`

Set it up in every repository that releases, before the first run. GitHub creates a missing environment on the first
run, without any rules.

1. Deployment branches "Selected branches and tags" with the branches releases start from, e.g. `main` and
   `[0-9][0-9][0-9][0-9].[0-9][0-9].x`.
2. A branch ruleset for the same patterns with "Restrict creations", with the maintainers and the GitHub App as bypass
   actors. Otherwise somebody with write permission creates a branch of a matching name with a workflow of their own
   and gets the secrets.
3. The release secrets as environment secrets. Do not share organization secrets of the same names with the
   repository, they stay readable from every branch.

The environment protects the secrets from other branches. Against code of the build, the jobs protect them: releases,
version branches and snapshot deploys run code of the project only in jobs without secrets, see
[`maven-release.yml`](docs/maven-release.md#secrets-and-push-access) and
[`maven-deploy.yml`](docs/maven-deploy.md#how-it-works).

### Push access

Releases and version branches push to protected branches with a GitHub App of the organization:

- Repository permission "Contents: Read and write", installed only on the repositories that release.
- Bypass actor of the branch and tag rulesets of these repositories.
- Its client ID in the organization variable `RELEASE_APP_CLIENT_ID`, its private key as `RELEASE_APP_PRIVATE_KEY`
  in the environment `release`.

The workflows create a token right before each push, valid for one hour and only for the repository of the run.
Without `RELEASE_APP_CLIENT_ID` they push with `GITHUB_TOKEN`, which fails on protected branches and starts no workflows.
Do not make GitHub Actions itself a bypass actor of a ruleset, then every workflow on every branch could push past it.

### Variables

The workflows read these organization variables from the calling repository, like the ones of the
[notifications](#notifications):

| Variable                | Used by                                         | Content                                                                         |
|-------------------------|-------------------------------------------------|---------------------------------------------------------------------------------|
| `RELEASE_APP_CLIENT_ID` | `maven-release.yml`, `maven-version-branch.yml` | Client ID of the GitHub App that pushes                                         |
| `DISPATCH_ACTOR`        | `maven-release.yml`, `maven-version-branch.yml` | Login of the account of `DISPATCH_TOKEN`, refused as starter of these workflows |

## Notifications

Releases, version branches and failures of the snapshot refresh are reported to a Matrix room:

| Workflow                   | Message                                                                                           |
|----------------------------|---------------------------------------------------------------------------------------------------|
| `maven-release.yml`        | Released, released with a failing Docker push or GitHub release, failed or cancelled, rolled back |
| `maven-version-branch.yml` | Branch created or failed                                                                          |
| `node-release.yml`         | Published, published without GitHub release, failed                                               |
| `snapshot-refresh.yml`     | Failed, with the failing targets                                                                  |

The room is set by organization variables, which the workflows read from the calling repository:

| Variable            | Example              | Content                                   |
|---------------------|----------------------|-------------------------------------------|
| `MATRIX_HOMESERVER` | `https://matrix.org` | Base URL of the homeserver                |
| `MATRIX_ROOM_ID`    | `!AbCdEf:matrix.org` | Internal id of the room, see its settings |

A repository variable with the same name sends the messages of that repository to another room.
Without the variables or without `MATRIX_ACCESS_TOKEN`, no message is sent and nothing fails.

The messages come from a separate Matrix account, which has to be a member of the room. Its access token is shown
in Element under Settings, Help & About. The room should not be end-to-end encrypted, as the messages are sent unencrypted.

## Versioning

Workflows and actions are released together. Use a major tag (`@v1`) in callers.
Workflows reference the actions of this repository with the self-repository syntax (`uses: $/.github/actions/...`),
which resolves to the commit of the running workflow. A caller referencing a branch, a tag or a commit SHA
therefore runs the actions of exactly that state. The syntax needs runner 2.336.0 or newer.

Every project runs `@v1` with its secrets, the signing key and the Central token included. Whoever can push to `main`
of this repository or move `v1` therefore controls the releases of all projects. Protect `main` with required reviews,
and the tags `v*` with a tag ruleset that lets only the maintainers of this repository create, move or delete them.

Release a change in this order:

1. Push it to a branch and run the affected workflows from a test project referencing `@<branch>`
2. Merge it, tag the version, e.g. `v1.4.0`, and move `v1` to it
3. If `workflow-templates` changed, copy its files to `workflow-templates` of `MyCoRe-Org/.github`

Third-party actions are pinned to commit SHAs and updated by Dependabot. Minor and patch updates come in one
pull request, every major update in a pull request of its own, as it needs a look at the release notes.
Tools the workflows call directly are pinned by hand, Dependabot does not see them: actionlint and zizmor in
[`lint.yml`](docs/lint.md), Corepack in `node-setup` and `maven-help-plugin` in the Maven workflows.

## License

[GPL-3.0](LICENSE.txt)
