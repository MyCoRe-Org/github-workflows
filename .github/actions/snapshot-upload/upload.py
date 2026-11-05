#!/usr/bin/env python3
"""Checks the snapshots the central-publishing-maven-plugin staged in STAGING and writes WORK/pom.xml, which
uploads them to SNAPSHOT_URL.

STAGING is the directory central-deferred the plugin leaves with skipUpload, a repository whose files carry the snapshot
version without timestamp, described by the metadata maven-metadata-central-staging.xml. Only components of the project
in PROJECT are allowed, the project and its modules, also those of profiles, each in the version of its pom with
QUALIFIER added. The pom of WORK runs maven-deploy-plugin:deploy-file in PLUGIN_VERSION for every component, with the
coordinates of its pom in PROJECT, so the repository keeps its snapshot metadata. No pom of the project is run, they
are only read."""
import os
import re
import sys
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape

# the components of the project are read like central-bundle-check reads them for a release, without leaving
# bytecode in the directory of the action
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "central-bundle-check"))
from pom_components import NAME, components, fail, has_control  # noqa: E402

# metadata of the staging repository of the plugin
METADATA = "maven-metadata-central-staging.xml"
# list of the staged files the plugin writes beside them, the metadata names the same files. upload-artifact leaves
# hidden files out, so it only shows up when the directory is passed on otherwise
INDEX = ".index"


def layout(coordinates):
    """directory of groupId:artifactId in a repository"""
    group, artifact = coordinates.split(":")
    return f"{group.replace('.', '/')}/{artifact}"


def snapshot_versions(metadata):
    """(classifier, extension, value) of the snapshot metadata of a version"""
    root = ElementTree.parse(metadata).getroot()
    for element in root.iter():  # the namespace of the metadata differs between Maven versions
        element.tag = element.tag.split("}")[-1]
    entries = []
    for entry in root.findall("versioning/snapshotVersions/snapshotVersion"):
        entries.append((entry.findtext("classifier") or "", entry.findtext("extension") or "", entry.findtext("value") or ""))
    return entries


def main():
    staging, project = Path(os.environ["STAGING"]).resolve(), Path(os.environ.get("PROJECT", ".")).resolve()
    qualifier, plugin = os.environ.get("QUALIFIER", ""), os.environ.get("PLUGIN_VERSION", "")
    url = os.environ.get("SNAPSHOT_URL") or "https://central.sonatype.com/repository/maven-snapshots/"
    work = Path(os.environ["WORK"])
    if qualifier and not NAME.fullmatch(qualifier):
        fail(f"the qualifier '{qualifier}' may only contain letters, digits, '.', '_' and '-'")
    if not re.fullmatch(r"3\.[1-9][0-9]*\.[0-9]+", plugin):
        fail(f"'{plugin}' is no version 3.1 or newer of the maven-deploy-plugin")

    expected, missing = {}, []
    for coordinates, version in components(project, missing=missing).items():
        if not version.endswith("-SNAPSHOT"):
            fail(f"{coordinates} has the version {version}, only snapshots are uploaded")
        expected[coordinates] = f"{version[:-len('-SNAPSHOT')]}-{qualifier}-SNAPSHOT" if qualifier else version

    # every file below <group path>/<artifactId>/ of a component, in its version
    found = {}
    for path in sorted(staging.rglob("*")):
        relative = path.relative_to(staging).as_posix()
        # the build wrote the names
        if has_control(relative):
            fail("the staging directory contains a name with a control character")
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            fail(f"the staging directory contains the link or special file {relative}")
        if path.is_dir() or relative == INDEX:
            continue
        owners = [c for c in expected if relative.startswith(layout(c) + "/")]
        if not owners:
            # e.g. a module in a submodule that is not checked out
            unread = f", and the checkout has no {', '.join(missing)}" if missing else ""
            fail(f"{relative} belongs to no component of the project, only those are uploaded{unread}")
        owner = max(owners, key=lambda c: len(layout(c)))
        rest = relative[len(layout(owner)) + 1:].split("/")
        if len(rest) == 1 and rest[0].startswith(METADATA):
            continue
        if len(rest) != 2 or rest[0] != expected[owner]:
            fail(f"{relative} is not in the version {expected[owner]} of {owner}")
        found.setdefault(owner, []).append(rest[1])

    executions = []
    for owner, files in sorted(found.items()):
        group, artifact = owner.split(":")
        version = expected[owner]
        directory = staging / layout(owner) / version
        if METADATA not in files:
            fail(f"{owner}:{version} has no snapshot metadata")
        pom, plain, attached, used = None, [], [], set()
        # the files carry the version itself, deploy-file gives them a timestamp in the repository
        for classifier, extension, value in snapshot_versions(directory / METADATA):
            if value != version or not NAME.fullmatch(extension) or (classifier and not NAME.fullmatch(classifier)):
                fail(f"the snapshot metadata of {owner}:{version} names '{classifier}' '{extension}' '{value}'")
            name = f"{artifact}-{value}{'-' + classifier if classifier else ''}.{extension}"
            if name not in files or name in used:
                fail(f"{owner}:{version} lacks {name} or names it twice")
            used.add(name)
            if classifier:
                attached.append((directory / name, classifier, extension))
            elif extension == "pom":
                pom = directory / name
            else:
                plain.append((directory / name, "", extension))
        # deploy-file takes an empty list of classifiers for a missing one, so a single file without classifier is
        # the main file. Several, like the archives of an assembly with appendAssemblyId false, are attached to the pom
        main, packaging = (plain[0][0], plain[0][2]) if len(plain) == 1 else (None, "pom")
        if main is None:
            attached = plain + attached
        unknown = [f for f in files if f not in used and not re.search(r"(\.md5|\.sha1|\.sha256|\.sha512)$", f)
                   and not f.startswith(METADATA)]
        if pom is None or unknown:
            fail(f"{owner}:{version} has no pom or unknown files: {', '.join(unknown)}")
        # without the coordinates, deploy-file would take them from the pom of the build
        configuration = {"groupId": group, "artifactId": artifact, "version": version, "packaging": packaging,
                         "file": main or pom, "pomFile": pom, "generatePom": "false", "url": url,
                         "repositoryId": "central", "retryFailedDeploymentCount": "3"}
        if attached:
            configuration["files"] = ",".join(str(f) for f, _, _ in attached)
            configuration["classifiers"] = ",".join(c for _, c, _ in attached)
            configuration["types"] = ",".join(t for _, _, t in attached)
        executions.append((owner, version, configuration))

    if not executions:
        fail("the build staged nothing")
    work.mkdir(parents=True, exist_ok=True)
    blocks = []
    for number, (owner, version, configuration) in enumerate(executions, 1):
        values = "".join(f"<{key}>{escape(str(value))}</{key}>" for key, value in configuration.items())
        blocks.append(f"<execution><id>component-{number}</id><phase>validate</phase><goals><goal>deploy-file</goal></goals>"
                      f"<configuration>{values}</configuration></execution>")
        names = [Path(str(configuration["file"])).name] + [Path(f).name for f in configuration.get("files", "").split(",") if f]
        print(f"uploading {owner}:{version} with {', '.join(names)}")
    (work / "pom.xml").write_text(
        '<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>'
        "<groupId>snapshot-upload</groupId><artifactId>snapshot-upload</artifactId><version>1</version><packaging>pom</packaging>"
        f"<build><plugins><plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-deploy-plugin</artifactId>"
        f"<version>{plugin}</version><executions>{''.join(blocks)}</executions></plugin></plugins></build></project>\n")


main()
