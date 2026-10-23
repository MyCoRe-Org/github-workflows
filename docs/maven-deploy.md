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

Every version branch has its own copy of the file with the Java version of that branch,
e.g. `'17'` on `2023.06.x` and `'25'` on `2026.06.x`.

To rebuild dependent projects after the deploy, add a job with [`dispatch-downstream.yml`](dispatch-downstream.md).

## Requirements

`mycore-parent` 57 or newer. It brings the `central-publishing-maven-plugin` in the profile `deploy-to-central`,
active by default, with the server id `central`. Snapshots go to `https://central.sonatype.com/repository/maven-snapshots`.
Up to version 56 the parent deploys to OSSRH, which is shut down, so the deploy fails.
There is no profile parameter, the deploy configuration comes from the parent only.

## Inputs

| Input               | Required | Default | Description                                                                                                                  |
|---------------------|----------|---------|------------------------------------------------------------------------------------------------------------------------------|
| `java-version`      | yes      |         | Java version, e.g. `'25'`                                                                                                    |
| `skip-tests`        | no       | `false` | Deploy without running the tests again                                                                                       |
| `setup-browser`     | no       | `false` | See [`maven-build.yml`](maven-build.md)                                                                                      |
| `project-setup`     | no       | `false` | See [`maven-build.yml`](maven-build.md#project-setup)                                                                        |
| `docker-images`     | no       |         | Images to push after the deploy, see [Docker images](#docker-images)                                                         |
| `docker-date-tag`   | no       | `false` | Additionally tag the images with `<branch>-<date>`                                                                           |
| `version-qualifier` | no       |         | Deploy `<version>-<qualifier>-SNAPSHOT` instead of `<version>-SNAPSHOT`, used by [`maven-deploy-pr.yml`](maven-deploy-pr.md) |

| Secret                                   | Description                                   |
|------------------------------------------|-----------------------------------------------|
| `MAVEN_USERNAME`                         | Sonatype Central token username               |
| `MAVEN_PASSWORD`                         | Sonatype Central token password               |
| `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` | Docker Hub login, needed with `docker-images` |

## How it works

1. [`maven-setup`](../.github/actions/maven-setup/action.yml) checks out the branch, sets up the JDK and writes
   a Maven `settings.xml` with the server `central`, which reads its credentials from `MAVEN_USERNAME` and `MAVEN_PASSWORD`.
2. With `version-qualifier`, `versions:set` changes the version of all modules, e.g. `2026.06.1-SNAPSHOT` with the
   qualifier `test` to `2026.06.1-test-SNAPSHOT`. The qualifier may only contain letters, digits, `.`, `_` and `-`,
   and the project must have a snapshot version.
3. `mvn deploy` builds, runs the tests unless `skip-tests` is set, and uploads the snapshot.
4. With `docker-images`, the images are built and pushed.

`skip-tests` saves time when the same commit was already tested, e.g. by the checks of its pull request.

## Docker images

`docker-images` lists one image per line as `<image> <context> [<dockerfile>]`, the Dockerfile defaults to
`<context>/Dockerfile`. The Dockerfiles copy the built war, so they run after Maven.

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
