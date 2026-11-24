#!/usr/bin/env python3
"""Writes the Maven section of the release notes to OUTPUT: a dependency for every component of COORDINATES with a jar
or war, and a table with the links to its files on Maven Central. COORDINATES names one component of BUNDLE per line,
as groupId:artifactId or as artifactId alone. The entries of the bundle are only read, nothing is extracted."""
import os
import sys
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "central-bundle-check"))
from pom_components import NAME, fail  # noqa: E402

CHECKSUMS = (".md5", ".sha1", ".sha256", ".sha512", ".asc")
REPOSITORY = "https://repo1.maven.org/maven2"
CENTRAL = "https://central.sonatype.com/artifact"


def read_bundle(bundle, version):
    result = {}
    try:
        with zipfile.ZipFile(bundle) as archive:
            names = archive.namelist()
    except Exception as error:
        fail(f"the bundle cannot be read as zip file: {error!r}")
    for name in names:
        if name.endswith("/") or name.endswith(CHECKSUMS):
            continue
        parts = name.split("/")
        if len(parts) < 4 or any(part in (".", "..") or not NAME.fullmatch(part) for part in parts):
            fail(f"the bundle contains {name}, which is no file of a Maven component")
        group, (artifact, directory, file) = parts[:-3], parts[-3:]
        prefix = f"{artifact}-{version}"
        if directory != version or not file.startswith((f"{prefix}.", f"{prefix}-")):
            fail(f"the bundle contains {name}, which is no file of a component in version {version}")
        result.setdefault(f"{'.'.join(group)}:{artifact}", []).append(file[len(prefix):])
    return result


def select(components, coordinates):
    selected = []
    for line in coordinates.splitlines():
        wanted = line.strip()
        if not wanted:
            continue
        if not all(NAME.fullmatch(part) for part in wanted.split(":")) or wanted.count(":") > 1:
            fail(f"release-coordinates has '{wanted}', expected groupId:artifactId or artifactId")
        if ":" in wanted:
            matches = [wanted] if wanted in components else []
        else:
            matches = [key for key in components if key.split(":")[1] == wanted]
        if not matches:
            fail(f"release-coordinates names {wanted}, but the bundle for Central has no such component")
        if len(matches) > 1:
            fail(f"release-coordinates names {wanted}, which is {' and '.join(sorted(matches))}, give the groupId")
        if matches[0] not in selected:
            selected.append(matches[0])
    return selected


def split(suffix):
    if suffix.startswith("."):
        return "", suffix[1:]
    classifier, _, extension = suffix[1:].partition(".")
    return classifier, extension


def main():
    version = os.environ["VERSION"]
    components = read_bundle(os.environ["BUNDLE"], version)
    selected = select(components, os.environ.get("COORDINATES", ""))
    if not selected:
        fail("release-coordinates names no component")

    dependencies, rows = [], []
    for key in selected:
        group, artifact = key.split(":")
        base = f"{REPOSITORY}/{group.replace('.', '/')}/{artifact}/{version}"
        files = sorted(split(suffix) for suffix in components[key])

        def link(classifier, extension):
            label = extension if not classifier else classifier if extension == "jar" else f"{classifier}.{extension}"
            name = f"{artifact}-{version}{'-' + classifier if classifier else ''}.{extension}"
            return f"[{label}]({base}/{name})"

        mains = [extension for classifier, extension in files if not classifier and extension != "pom"]
        if "jar" in mains or "war" in mains:
            dependency = ["<dependency>", f"  <groupId>{group}</groupId>", f"  <artifactId>{artifact}</artifactId>",
                          f"  <version>{version}</version>"]
            if "jar" not in mains:
                dependency.append("  <type>war</type>")
            dependencies.append("\n".join(dependency + ["</dependency>"]))

        binaries = [link(c, e) for c, e in files if not c and e != "pom"]
        sources = [link(c, e) for c, e in files if c == "sources"]
        javadoc = [link(c, e) for c, e in files if c == "javadoc"]
        pom = [link(c, e) for c, e in files if not c and e == "pom"]
        cells = [f"[{artifact}]({CENTRAL}/{group}/{artifact}/{version})"]
        cells += [", ".join(column) for column in (binaries, sources, javadoc, pom)]
        rows.append("| " + " | ".join(cells) + " |")

    sections = []
    if dependencies:
        sections.append("## Maven\n\n```xml\n" + "\n\n".join(dependencies) + "\n```")
    sections.append("## Download\n\n| Artifact | Binary | Sources | Javadoc | POM |\n| --- | --- | --- | --- | --- |\n"
                    + "\n".join(rows))
    output = Path(os.environ["OUTPUT"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
    print(f"the release notes name {len(selected)} components, {len(dependencies)} of them as dependency")


main()
