#!/usr/bin/env bash
# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
#
# Build a source release for a tag: tarball (no images, binaries or model
# weights) + sha256 + license declaration. Publishes with `gh` only when
# --publish is given; otherwise it is a dry run into dist/.
#   scripts/make-release.sh v1.0.0 [--publish]
set -euo pipefail
cd "$(dirname "$0")/.."
tag="${1:?usage: make-release.sh <tag> [--publish]}"
git rev-parse -q --verify "refs/tags/$tag" >/dev/null || { echo "tag $tag does not exist"; exit 1; }
name="clew-${tag#v}"
mkdir -p dist
git archive --format=tar.gz --prefix="$name/" -o "dist/$name.tar.gz" "$tag"
(cd dist && shasum -a 256 "$name.tar.gz" > "$name.tar.gz.sha256")
cp docs/license-declaration.csv "dist/$name-license-declaration.csv"
echo "Built dist/$name.tar.gz ($(du -h "dist/$name.tar.gz" | cut -f1))"
cat "dist/$name.tar.gz.sha256"
# The CHANGELOG section of a version: lines after its "## [x.y.z]" heading up to the
# next "## [" heading or the end of the file (the oldest section has no next heading).
release_notes() { awk -v h="## [$1]" '/^## \[/ { p = (index($0, h) == 1); next } p' CHANGELOG.md; }

if [[ "${2:-}" == "--publish" ]]; then
  gh release create "$tag" "dist/$name.tar.gz" "dist/$name.tar.gz.sha256" "dist/$name-license-declaration.csv" \
    --title "Clew $tag" --notes-file <(release_notes "${tag#v}")
fi
