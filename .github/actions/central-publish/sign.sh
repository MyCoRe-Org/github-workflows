#!/usr/bin/env bash
set -euo pipefail

# Every file of BUNDLE must belong to a component of GROUP_ID_PREFIX in VERSION. All files but the checksums are
# signed with GPG_PRIVATE_KEY, the signatures get checksums like the other files, and the result is SIGNED_BUNDLE.

fail() {
  echo "::error::$1"
  exit 1
}

# <group path>/<artifactId>/<version>/<artifactId>-<version>[-<classifier>].<extension>, checked before extracting
PREFIX="${GROUP_ID_PREFIX//.//}/"
ENTRIES="$(unzip -Z1 "$BUNDLE" 2> /dev/null)" || fail "the bundle is empty or no zip file"
COUNT=0
while IFS= read -r entry; do
  [[ "$entry" == */ ]] && continue
  dir="${entry%/*}"
  file="${entry##*/}"
  artifact="${dir%/*}"
  artifact="${artifact##*/}"
  if [[ "$entry" != "$PREFIX"* ]] || [[ "/${entry}/" == */../* ]] || [ "${dir##*/}" != "$VERSION" ] \
    || [[ "$file" != "${artifact}-${VERSION}."* && "$file" != "${artifact}-${VERSION}-"* ]] || [[ "$file" == *.asc* ]]; then
    fail "the bundle contains ${entry}, only unsigned files of ${GROUP_ID_PREFIX} in version ${VERSION} are published"
  fi
  COUNT=$((COUNT + 1))
done <<< "$ENTRIES"
[ "$COUNT" -gt 0 ] || fail "the bundle is empty"

WORK="$(mktemp -d)"
GNUPGHOME="$(mktemp -d)"
export GNUPGHOME
trap 'gpgconf --kill gpg-agent > /dev/null 2>&1 || true; rm -rf "$WORK" "$GNUPGHOME"' EXIT
unzip -q "$BUNDLE" -d "$WORK"
[ -z "$(find "$WORK" ! -type f ! -type d -print -quit)" ] || fail "the bundle contains links or other special files"

gpg --batch --quiet --import <<< "$GPG_PRIVATE_KEY"
echo "signing with $(gpg --batch --list-secret-keys --with-colons | awk -F: '$1 == "fpr" { print $10; exit }')"
find "$WORK" -type f ! -name '*.md5' ! -name '*.sha1' ! -name '*.sha256' ! -name '*.sha512' -print0 \
  | while IFS= read -r -d '' file; do
      gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-fd 0 --armor --detach-sign "$file" \
        <<< "$GPG_PASSPHRASE"
      for algorithm in md5 sha1 sha256 sha512; do
        printf '%s' "$("${algorithm}sum" "${file}.asc" | cut -d ' ' -f 1)" > "${file}.asc.${algorithm}"
      done
    done

SIGNED="$(find "$WORK" -type f -name '*.asc' | wc -l)"
[ "$SIGNED" -gt 0 ] || fail "the bundle contains nothing to sign, only checksums"
rm -f "$SIGNED_BUNDLE"
(cd "$WORK" && zip -q -r -X "$SIGNED_BUNDLE" .)
echo "signed ${SIGNED} files of ${GROUP_ID_PREFIX} ${VERSION}"
