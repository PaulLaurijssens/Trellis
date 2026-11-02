#!/usr/bin/env bash
# Build the release bundle: trellis-bundle.zip (top folder trellis/) + SHA256SUMS.
#   scripts/make-bundle.sh [--out dist] [--allow-missing-installer]
# The bundle runs the ready-made images from ghcr.io, so its compose.yaml has no build sections.
# The image tag stays ${TRELLIS_VERSION:-latest}: the installer and .env pick the version.
# The release workflow runs this; run it locally to test a bundle before a tag.
set -euo pipefail

OUT="dist"
ALLOW_MISSING=0
while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT="${2:?--out needs a folder}"; shift 2 ;;
    --allow-missing-installer) ALLOW_MISSING=1; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
B="$STAGE/trellis"
mkdir -p "$B/deploy" "$B/backups" "$B/scripts" "$B/docs"

# The installer scripts may live at the top of the repo or in a subfolder.
find_installer() {
  for dir in "" scripts/ installer/; do
    if [ -f "$ROOT/$dir$1" ]; then echo "$ROOT/$dir$1"; return 0; fi
  done
  return 1
}

# compose.yaml without the build sections: drop each "build:" key and every deeper-indented line under it.
awk '
  skip && (/^[[:space:]]*$/ || match($0, /^ */) && RLENGTH > indent) { next }
  { skip = 0 }
  /^[[:space:]]+build:/ { match($0, /^ */); indent = RLENGTH; skip = 1; next }
  { print }
' "$ROOT/compose.yaml" | sed -e '/^# Source checkout:/,/always builds from source/d' -e '/^# Developers:/d' > "$B/compose.yaml"
if grep -qE '^[[:space:]]+(build|context|dockerfile):' "$B/compose.yaml"; then
  echo "make-bundle: a build section is left in compose.yaml" >&2; exit 1
fi

cp "$ROOT/.env.example" "$ROOT/README.md" "$ROOT/LICENSE" "$B/"
cp "$ROOT/deploy/nginx.conf" "$B/deploy/"
cp -R "$ROOT/db" "$B/db"
touch "$B/backups/.gitkeep"
cp "$ROOT/scripts/restore.sh" "$B/scripts/"
cp "$ROOT/docs/VPS.md" "$ROOT/docs/PROVIDERS.md" "$B/docs/"     # the README links to them

rm -f "$OUT/trellis-bundle.zip" "$OUT/setup.sh" "$OUT/setup.ps1" "$OUT/SHA256SUMS"
for f in setup.sh setup.ps1; do
  if src="$(find_installer "$f")"; then
    cp "$src" "$B/$f"
    cp "$src" "$OUT/$f"                 # also a release asset of its own (the one-line install)
  elif [ "$ALLOW_MISSING" = 1 ]; then
    echo "make-bundle: warning: $f not found, the bundle has no $f" >&2
  else
    echo "make-bundle: $f not found (looked in ./, scripts/, installer/)" >&2; exit 1
  fi
done
chmod 0755 "$B/scripts/restore.sh"
[ -f "$B/setup.sh" ] && chmod 0755 "$B/setup.sh"

(cd "$STAGE" && zip -qrX "$OUT/trellis-bundle.zip" trellis)

(cd "$OUT" && files=(trellis-bundle.zip); for f in setup.sh setup.ps1; do [ -f "$f" ] && files+=("$f"); done
 if command -v sha256sum >/dev/null; then sha256sum "${files[@]}"; else shasum -a 256 "${files[@]}"; fi > SHA256SUMS)

echo "make-bundle: $OUT/trellis-bundle.zip"
cat "$OUT/SHA256SUMS"
