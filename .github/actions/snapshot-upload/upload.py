#!/usr/bin/env python3
"""Checks the snapshots a build deployed into STAGING and writes WORK/pom.xml, which uploads them to SNAPSHOT_URL.

Only components of the project in PROJECT are allowed, the project and its modules, also those of profiles, each in
the version of its pom with QUALIFIER added. The pom of WORK runs maven-deploy-plugin:deploy-file in PLUGIN_VERSION for
every component, with the coordinates of its pom in PROJECT, so the repository keeps its snapshot metadata. No pom of
the project is run, they are only read."""
import os
import re
import sys
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape

POM = "{http://maven.apache.org/POM/4.0.0}"
NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def fail(message):
    print(f"::error::{message}")
    sys.exit(1)


def text(element, *path):
    for name in path:
        element = None if element is None else element.find(POM + name)
    return element.text.strip() if element is not None and element.text else None


def components(project):
    """groupId:artifactId of the project and its modules mapped to their versions"""
    result, todo, seen = {}, [project / "pom.xml"], set()
    while todo:
        pom = todo.pop().resolve()
        if pom in seen:
            continue
        seen.add(pom)
        if project not in pom.parents:
            fail(f"the module {pom} lies outside of the project")
        if not pom.is_file():
            print(f"::warning::{pom.relative_to(project)} does not exist, the module is not uploaded")
            continue
        root = ElementTree.parse(pom).getroot()
        group = text(root, "groupId") or text(root, "parent", "groupId")
        artifact = text(root, "artifactId")
        version = text(root, "version") or text(root, "parent", "version")
        # also keeps commas out of the lists of deploy-file
        if not all(NAME.fullmatch(value or "") for value in (group, artifact, version)):
            fail(f"{pom.relative_to(project)} has no plain groupId, artifactId and version")
        result[f"{group}:{artifact}"] = version
        modules = root.findall(f"{POM}modules/{POM}module") + root.findall(f"{POM}profiles/{POM}profile/{POM}modules/{POM}module")
        for module in modules:
            path = pom.parent / module.text.strip()
            todo.append(path if path.suffix == ".xml" else path / "pom.xml")
    return result


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

    expected = {}
    for coordinates, version in components(project).items():
        if not version.endswith("-SNAPSHOT"):
            fail(f"{coordinates} has the version {version}, only snapshots are uploaded")
        expected[coordinates] = f"{version[:-len('-SNAPSHOT')]}-{qualifier}-SNAPSHOT" if qualifier else version

    # every file below <group path>/<artifactId>/ of a component, in its version
    found = {}
    for path in sorted(staging.rglob("*")):
        relative = path.relative_to(staging).as_posix()
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            fail(f"the staging directory contains the link or special file {relative}")
        if path.is_dir():
            continue
        owners = [c for c in expected if relative.startswith(layout(c) + "/")]
        if not owners:
            fail(f"{relative} belongs to no component of the project, only those are uploaded")
        owner = max(owners, key=lambda c: len(layout(c)))
        rest = relative[len(layout(owner)) + 1:].split("/")
        if len(rest) == 1 and rest[0].startswith("maven-metadata.xml"):
            continue
        if len(rest) != 2 or rest[0] != expected[owner]:
            fail(f"{relative} is not in the version {expected[owner]} of {owner}")
        found.setdefault(owner, []).append(rest[1])

    executions = []
    for owner, files in sorted(found.items()):
        group, artifact = owner.split(":")
        version = expected[owner]
        directory = staging / layout(owner) / version
        if "maven-metadata.xml" not in files:
            fail(f"{owner}:{version} has no snapshot metadata")
        base = re.escape(version[:-len("-SNAPSHOT")])
        pom, plain, attached, used = None, [], [], set()
        for classifier, extension, value in snapshot_versions(directory / "maven-metadata.xml"):
            if not re.fullmatch(rf"{base}-[0-9]{{8}}\.[0-9]{{6}}-[0-9]+", value) or not NAME.fullmatch(extension) \
                    or (classifier and not NAME.fullmatch(classifier)):
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
                   and not f.startswith("maven-metadata.xml")]
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
        fail("the build deployed nothing")
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
