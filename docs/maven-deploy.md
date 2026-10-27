# maven-deploy.yml

Deploys the snapshot of the current branch to Sonatype Central and optionally builds and pushes Docker images.

## Usage

```yaml
name: Maven Snapshot Deploy

on:
  push:
    branches:
      - main
      - '[0-9][0-9][0-9][0-9].[0-9][0-9].x'
  workflow_dispatch:

permissions:
  contents: read

jobs:
  deploy:
    concurrency:
      group: snapshot-deploy-${{ github.repository }}-${{ github.ref_name }}
      cancel-in-progress: true
    uses: MyCoRe-Org/github-workflows/.github/workflows/maven-deploy.yml@v1
    with:
      java-version: '25'
    secrets:
      MAVEN_USERNAME: ${{ secrets.MAVEN_USERNAME }}
      MAVEN_PASSWORD: ${{ secrets.MAVEN_PASSWORD }}
```

Keep `workflow_dispatch`. It allows a redeploy by hand, and it is how [`dispatch-downstream.yml`](dispatch-downstream.md)
and the weekly [snapshot refresh](snapshot-refresh.md) start the deploy. The examples name this file `maven-snapshot.yml`.
"Run workflow" works on every branch, an [environment](#environment) restricts it to the snapshot branches.

Every version branch has its own copy of the file with the Java version of that branch,
e.g. `'17'` on `2023.06.x` and `'25'` on `2026.06.x`.

To rebuild dependent projects after the deploy, add a job with [`dispatch-downstream.yml`](dispatch-downstream.md).

## Requirements

`mycore-parent` 57 or newer, so the version branches since `2023.06.x` deploy as well. Snapshots go to
`https://central.sonatype.com/repository/maven-snapshots`, the snapshot repository the parent configures.
The upload uses the `maven-deploy-plugin` in the version the parent manages, the build switches the profile
`deploy-to-central` off. Up to version 56 the parent deploys to OSSRH, which is shut down. Without the property
`maven-deploy-plugin.version` of the parent the run fails before the build.

## Inputs

| Input               | Required | Default | Description                                                                                                                  |
|---------------------|----------|---------|------------------------------------------------------------------------------------------------------------------------------|
| `java-version`      | yes      |         | Java version, e.g. `'25'`                                                                                                    |
| `skip-tests`        | no       | `false` | Deploy without running the tests again                                                                                       |
| `build-args`        | no       |         | Arguments of the build, e.g. `-Dtomcat`, see [Examples](#examples)                                                           |
| `maven-opts`        | no       |         | `MAVEN_OPTS` of the build, e.g. `-Xss128M`                                                                                   |
| `setup-browser`     | no       | `false` | See [`maven-build.yml`](maven-build.md)                                                                                      |
| `project-setup`     | no       | `false` | See [`maven-build.yml`](maven-build.md#project-setup)                                                                        |
| `docker-images`     | no       |         | Images to push after the deploy, see [Docker images](#docker-images)                                                         |
| `docker-date-tag`   | no       | `false` | Additionally tag the images with `<branch>-<date>`                                                                           |
| `version-qualifier` | no       |         | Deploy `<version>-<qualifier>-SNAPSHOT` instead of `<version>-SNAPSHOT`, used by [`maven-deploy-pr.yml`](maven-deploy-pr.md) |
| `environment`       | no       |         | Environment of the jobs with secrets, e.g. `snapshot`, see [Environment](#environment)                                       |

| Secret                                   | Description                                   |
|------------------------------------------|-----------------------------------------------|
| `MAVEN_USERNAME`                         | Sonatype Central token username               |
| `MAVEN_PASSWORD`                         | Sonatype Central token password               |
| `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` | Docker Hub login, needed with `docker-images` |

## How it works

The deploy runs in three jobs, so code of the project, the tests, Maven plugins and npm packages included, never runs
with a secret:

| Job      | Secrets          | Code of the project | Does                                                          |
|----------|------------------|---------------------|---------------------------------------------------------------|
| `build`  | none             | yes                 | Builds and tests, deploys into a directory, builds the images |
| `deploy` | Central token    | no                  | Checks the directory, uploads the snapshots of the project    |
| `images` | Docker Hub login | no                  | Pushes the images of `build` with the tags of the branch      |

1. **build** checks out the commit with [`maven-setup`](../.github/actions/maven-setup/action.yml).
   - With `version-qualifier`, `versions:set` changes the version of all modules, e.g. `2026.06.1-SNAPSHOT` with the
     qualifier `test` to `2026.06.1-test-SNAPSHOT`. The qualifier may only contain letters, digits, `.`, `_` and `-`,
     and the project must have a snapshot version.
   - `mvn deploy -DskipDeployToCentral` with `build-args` builds, runs the tests unless `skip-tests` is set, and
     deploys into a directory instead of uploading. Modules with `maven.deploy.skip` are left out. `build-args`
     cannot change where the snapshots go, only deploy uploads them. `versions:set` gets `build-args` as well.
   - With `docker-images`, it builds the images and saves them for the job `images`.
2. **deploy** checks out the commit again, but only reads its poms, with
   [`snapshot-upload`](../.github/actions/snapshot-upload/action.yml).
   - Every file of the directory must belong to the project or one of its modules, also those of profiles, in the
     version of its pom with `version-qualifier`. Only snapshots are uploaded, links and other special files fail.
   - `maven-deploy-plugin:deploy-file` uploads the files of each module and updates the snapshot metadata of the
     repository like a deploy from the build would. groupId, artifactId and version come from the poms of the commit,
     not from the poms the build deployed.
   - Maven runs without cache and outside the checkout, so it reads no `.mvn` of the project.
3. **images** pushes the images of the job `build` after the upload, see [Docker images](#docker-images). Only the
   images of `docker-images` are pushed, with the tags it determines itself.

`skip-tests` saves time when the same commit was already tested, e.g. by the checks of its pull request.
A compromised dependency in the build can still change the snapshots it builds, but it reads no secret and uploads
nothing the poms of the commit do not declare.

## Environment

With `environment`, the jobs deploy and images run in that environment of the calling repository:

- Its deployment branches decide which branches may deploy, in the branch naming of the repository, e.g. `main` and
  `[0-9][0-9][0-9][0-9].[0-9][0-9].x`, or `main` and `mycore-*.x` for JSPDocportal. "Run workflow" on a feature
  branch then fails, instead of deploying it under the snapshot version of `main`. That also holds if the secrets
  stay organization secrets.
- Its secrets take precedence over organization secrets of the same name, the caller passes them on by name all the
  same. A repository that keeps the Central token from its other branches stores it there.
- Every run creates a deployment of the environment, two with images.

Create the environment before the first run, GitHub creates a missing one without any rules.
[`maven-deploy-pr.yml`](maven-deploy-pr.md) sets no environment, as the merge refs of pull requests match no
deployment branch.

## Docker images

`docker-images` lists one image per line as `<image> <context> [<dockerfile>]`, the Dockerfile defaults to
`<context>/Dockerfile`. The Dockerfiles copy the built war, so they run after Maven. The job `build` builds them
with [`docker-build`](../.github/actions/docker-build/action.yml) without any credentials, the job `images` pushes
them with [`docker-push`](../.github/actions/docker-push/action.yml).

```yaml
docker-images: |
  mycoreorg/<app> . Dockerfile
  mycoreorg/<app>-solr <app>-webapp/src/main/solr/
```

Snapshots are tagged with the branch name, with `docker-date-tag` additionally with `<branch>-<date>`,
the date of the run as `YYYY-MM-DD`. The branch name is lowercased, characters other than `a-z`, `0-9`, `.`, `_`
and `-` become `-`, leading `.` and `-` are removed and the name is cut to 117 characters,
so the tags stay within the Docker limit of 128 characters.
Releases are tagged with the version instead, see [`maven-release.yml`](maven-release.md#docker-images).

## Examples

Snapshot deploy with Docker images:

```yaml
jobs:
  deploy:
    uses: MyCoRe-Org/github-workflows/.github/workflows/maven-deploy.yml@v1
    with:
      java-version: '25'
      skip-tests: true
      docker-images: |
        mycoreorg/<app> . Dockerfile
        mycoreorg/<app>-solr <app>-webapp/src/main/solr/
      docker-date-tag: true
    secrets:
      MAVEN_USERNAME: ${{ secrets.MAVEN_USERNAME }}
      MAVEN_PASSWORD: ${{ secrets.MAVEN_PASSWORD }}
      DOCKERHUB_USERNAME: ${{ secrets.DOCKERHUB_USERNAME }}
      DOCKERHUB_TOKEN: ${{ secrets.DOCKERHUB_TOKEN }}
```

Snapshot deploy of `mir` on `2026.06.x`. Its module `mir-it` starts a servlet container even with `-DskipTests`, up
to `2026.06.x` only with `-Djetty` or `-Dtomcat`, as in the CI of the branch. On `main` Tomcat is the default:

```yaml
    with:
      java-version: '25'
      build-args: '-Dtomcat'
```
