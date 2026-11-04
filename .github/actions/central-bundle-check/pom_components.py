"""The components of a Maven project, read from its poms without running any of them.

check.py of central-bundle-check and upload.py of snapshot-upload import components()."""
import re
import sys
from pathlib import Path
from xml.etree import ElementTree

NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def fail(message):
    print(f"::error::{message}")
    sys.exit(1)


def has_control(text):
    """whether text has a line break or another control character, which in the log could start a workflow command"""
    return any(ord(c) < 32 or ord(c) == 127 for c in text)


def text(element, ns, *path):
    for name in path:
        element = None if element is None else element.find(ns + name)
    return element.text.strip() if element is not None and element.text else None


def components(project, versions=True, missing=None):
    """groupId:artifactId of the project and its modules, also those of profiles, mapped to their versions, which must
    be plain values only with versions. A module without its pom is no component, missing gets its path"""
    project = Path(project).resolve()
    result, todo, seen = {}, [project / "pom.xml"], set()
    while todo:
        pom = todo.pop().resolve()
        if pom in seen:
            continue
        seen.add(pom)
        if project not in pom.parents:
            fail(f"the module {pom} lies outside of the project")
        if not pom.is_file():
            print(f"::warning::{pom.relative_to(project)} does not exist, the module is no component")
            if missing is not None:
                missing.append(str(pom.relative_to(project)))
            continue
        try:
            root = ElementTree.parse(pom).getroot()
        except ElementTree.ParseError as error:
            fail(f"{pom.relative_to(project)} is no valid XML: {error}")
        # like Maven, also a pom without the namespace of POM 4.0.0, its elements are in the namespace of <project>
        ns = root.tag[: root.tag.find("}") + 1]
        group = text(root, ns, "groupId") or text(root, ns, "parent", "groupId")
        artifact = text(root, ns, "artifactId")
        version = text(root, ns, "version") or text(root, ns, "parent", "version")
        # also keeps commas out of the lists of deploy-file
        if not all(NAME.fullmatch(value or "") for value in (group, artifact) + ((version,) if versions else ())):
            fail(f"{pom.relative_to(project)} has no plain groupId, artifactId{' and version' if versions else ''}")
        result[f"{group}:{artifact}"] = version
        modules = root.findall(f"{ns}modules/{ns}module") + root.findall(f"{ns}profiles/{ns}profile/{ns}modules/{ns}module")
        for module in modules:
            name = (module.text or "").strip()
            if not name:
                fail(f"{pom.relative_to(project)} has an empty <module>")
            # the name ends up in the log
            if has_control(name):
                fail(f"{pom.relative_to(project)} has a <module> with a control character")
            path = pom.parent / name
            todo.append(path if path.suffix == ".xml" else path / "pom.xml")
    return result

