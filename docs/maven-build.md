# maven-build.yml

Builds and tests a Maven project, e.g. for pull requests and pushes.

## Usage

```yaml
name: Pull Request Checks

on:
  pull_request:

permissions:
  contents: read

jobs:
  build:
    concurrency:
      group: pr-checks-${{ github.repository }}-${{ github.event.pull_request.number }}
      cancel-in-progress: true
    uses: MyCoRe-Org/github-workflows/.github/workflows/maven-build.yml@v1
    with:
      java-version: '25'
```

The concurrency group cancels the build of an older commit when the pull request gets new commits.

## Inputs

| Input               | Required | Default               | Description                                                                        |
|---------------------|----------|-----------------------|------------------------------------------------------------------------------------|
| `java-version`      | yes      |                       | Java version, e.g. `'25'`                                                          |
| `maven-args`        | no       | `--batch-mode verify` | Maven arguments, one Maven invocation per line                                     |
| `maven-opts`        | no       |                       | `MAVEN_OPTS` for the build                                                         |
| `runs-on`           | no       | `ubuntu-latest`       | Runner label                                                                       |
| `submodules`        | no       | `false`               | Checkout submodules (`false`, `true`, `recursive`)                                 |
| `setup-browser`     | no       | `false`               | Put geckodriver and chromedriver on the `PATH` and select Firefox for Selenium     |
| `project-setup`     | no       | `false`               | Run the composite action `.github/actions/project-setup` of the calling repository |
| `failure-logs`      | no       |                       | Paths uploaded as artifact when the build fails                                    |
| `failure-logs-name` | no       | `test-results`        | Artifact name, must be unique per job, e.g. in a matrix                            |

The workflow needs no secrets.

## How it works

1. [`maven-setup`](../.github/actions/maven-setup/action.yml) checks out the repository without keeping the token,
   sets up the Temurin JDK with the Maven cache and points `TMPDIR` to a directory of the run. The Java problem
   matcher of `setup-java` is switched off, so compiler warnings do not become annotations.
2. With `setup-browser`, the geckodriver and chromedriver of the runner image are put on the `PATH`,
   `FIREFOX_BIN` and `SELENIUM_BROWSER=firefox` are set. This only works on GitHub-hosted Ubuntu runners,
   on other runners the step fails with an error.
3. With `project-setup`, the [project setup](#project-setup) of the calling repository runs.
4. Every non-empty line of `maven-args` is one Maven invocation with a log group of its own.
   The line is split at whitespace, quotes are not interpreted and patterns like `*` are passed on unchanged.
5. If the build fails or is cancelled and `failure-logs` is set, the matching files are uploaded as artifact `failure-logs-name`.

GitHub Actions sets `CI=true`. This activates the `ci` profile of `mycore-parent`, which among other things
verifies that the poms are sorted. Run `CI=true mvn verify` to reproduce such failures locally.

## Project setup

Steps only one project needs go into a composite action at `.github/actions/project-setup/action.yml`
in that project, enabled with `project-setup: true`. It runs after the checkout and the JDK setup,
in `maven-build.yml`, [`maven-deploy.yml`](maven-deploy.md) and [`maven-release.yml`](maven-release.md).

```yaml
name: Project Setup
description: Install additional tools needed by the build.

runs:
  using: composite
  steps:
    - name: Install tools
      shell: bash
      run: sudo apt-get install -y <package>
```

## Examples

Build with Selenium tests, several Maven runs and logs on failure:

```yaml
jobs:
  build:
    uses: MyCoRe-Org/github-workflows/.github/workflows/maven-build.yml@v1
    with:
      java-version: '25'
      setup-browser: true
      maven-args: |
        -B install
        -B javadoc:javadoc javadoc:test-javadoc
      failure-logs: |
        ./**/surefire-reports
        ./**/failsafe-reports
        ./**/screenshots
        ./**/*error*.log
```
