#!/usr/bin/env python3
"""Every file of BUNDLE must belong to a component of GROUP_ID_PREFIX in VERSION and must not be signed yet, and every
component must have its pom and every file its md5 and sha1. With PROJECT, the component must also be the project or
one of its modules, as the poms in PROJECT name them. The entries are read by zipfile and not by unzip, links and
entries that cannot be read are refused, nothing is extracted, and no pom is run."""
import os
import re
import stat
import sys
import zipfile
from pathlib import Path

# pom_components lies next to it, without a __pycache__ there
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pom_components import NAME, components, fail, has_control  # noqa: E402

# a signature and its checksums
SIGNED = re.compile(r"\.asc(\.(md5|sha1|sha256|sha512))?$")

# Central needs md5 and sha1 of every file, the plugin also writes sha256 and sha512
CHECKSUMS = (".md5", ".sha1", ".sha256", ".sha512")


def main():
    bundle, version, prefix = os.environ["BUNDLE"], os.environ["VERSION"], os.environ["GROUP_ID_PREFIX"]
    try:
        with zipfile.ZipFile(bundle) as archive:
            entries = archive.infolist()
            # publish extracts every entry, one that cannot be read would fail only after the push
            broken = archive.testzip()
    except Exception as error:  # anything zipfile cannot read, e.g. a name that is no UTF-8 or an unknown compression
        fail(f"the bundle cannot be read as zip file: {error!r}")
    project = os.environ.get("PROJECT", "")
    modules, missing = set(), []
    if project:
        # a release only needs groupId and artifactId, its version comes from the release
        modules = set(components(project, versions=False, missing=missing))
        if not modules:
            fail(f"the poms in {project} name no component")
    groups = prefix.split(".")
    found, poms, files, directories = set(), set(), set(), []
    for entry in entries:
        name = entry.filename
        # a line break or another control character would also end up in the log and in the names of the files
        if has_control(name):
            fail("the bundle contains a name with a control character")
        # zipfile would extract a link as a file that holds its target
        if stat.S_IFMT(entry.external_attr >> 16) not in (0, stat.S_IFREG, stat.S_IFDIR):
            fail(f"the bundle contains {name}, links and other special files are refused")
        if name.endswith("/"):
            directories.append(name)
            continue
        refused = f"the bundle contains {name}, only unsigned files of {prefix} in version {version} are published"
        # <group path>/<artifactId>/<version>/<artifactId>-<version>[-<classifier>].<extension>, each segment plain
        parts = name.split("/")
        if len(parts) < 4 or any(part in (".", "..") or not NAME.fullmatch(part) for part in parts):
            fail(refused)
        group, (artifact, directory, file) = parts[:-3], parts[-3:]
        # the groupId is the path before <artifactId>/<version>, the start of the entry is not enough. Maven writes no
        # dot into that path
        if (group[: len(groups)] != groups or any("." in part for part in group) or directory != version
                or not file.startswith((f"{artifact}-{version}.", f"{artifact}-{version}-")) or SIGNED.search(file)):
            fail(refused)
        coordinates = f"{'.'.join(group)}:{artifact}"
        if project and coordinates not in modules:
            # e.g. a module in a submodule that is not checked out
            unread = f", and the checkout has no {', '.join(missing)}" if missing else ""
            fail(f"the bundle contains {name}, but {coordinates} is neither the project nor one of its modules{unread}")
        # Central refuses a component without its pom
        component = "/".join(parts[:-2])
        found.add(component)
        if file == f"{artifact}-{version}.pom":
            poms.add(component)
        # extracting would keep only one of them
        if name in files:
            fail(f"the bundle contains {name} twice")
        files.add(name)
    if not files:
        fail("the bundle is empty")
    if broken is not None:
        fail(f"the bundle contains {broken}, which cannot be read")
    for component in sorted(found - poms):
        fail(f"the bundle has no {component}/{version}/{component.rsplit('/', 1)[1]}-{version}.pom, Central needs it")
    # sign.sh only adds the checksums of the signatures and signs no checksum, so each belongs to a file
    for name in sorted(files):
        if name.endswith(CHECKSUMS):
            checked = name.rsplit(".", 1)[0]
            if checked not in files or checked.endswith(CHECKSUMS):
                fail(f"the bundle contains {name}, but not the file it is the checksum of")
            continue
        for algorithm in ("md5", "sha1"):
            if f"{name}.{algorithm}" not in files:
                fail(f"the bundle has no {name}.{algorithm}, Central needs the md5 and sha1 of every file")
    # publish would extract and upload any other directory
    parents = {name[: i + 1] for name in files for i, c in enumerate(name) if c == "/"}
    for name in directories:
        if name not in parents:
            fail(f"the bundle contains {name}, only the directories of its files are published")
    print(f"the bundle holds {len(files)} files of {prefix} in version {version}"
          + (", all of the project and its modules" if project else ""))


main()
