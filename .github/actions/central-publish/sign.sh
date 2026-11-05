#!/usr/bin/env bash
set -euo pipefail

# Every file of BUNDLE must belong to a component of GROUP_ID_PREFIX in VERSION. All files but the checksums are
# signed with GPG_PRIVATE_KEY, the signatures get checksums like the other files, and the result is SIGNED_BUNDLE.

fail() {
  echo "::error::$1"
  exit 1
}

# the entries are checked before extracting, with the check push runs before anything is pushed. publish has no
# checkout, a PROJECT of the environment must not turn on the check of the modules
PROJECT='' python3 -I "$(dirname "${BASH_SOURCE[0]}")/../central-bundle-check/check.py"

WORK="$(mktemp -d)"
GNUPGHOME="$(mktemp -d)"
export GNUPGHOME
trap 'gpgconf --kill gpg-agent > /dev/null 2>&1 || true; rm -rf "$WORK" "$GNUPGHOME"' EXIT
# extracted with zipfile like the check reads it, not with unzip. The check refused links and other special files,
# zipfile would extract them as files
python3 -I -c 'import sys, zipfile
zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$BUNDLE" "$WORK"

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
