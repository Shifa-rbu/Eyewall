#!/usr/bin/env bash
# Assemble the Firebase Hosting public directory.
#
# Why this exists: static/app.js loads its map data from RELATIVE paths
# ("data/grid.json", "data/elev.i16", "data/assets.json", "data/tracks.json").
# On the FastAPI server /data is a separate mount, so that works. If Firebase
# published static/ alone, every one of those fetches would 404 and the map would
# never boot - the site would look broken while the deploy itself "succeeded".
#
# So the published directory must contain the static files AND data/. This
# script builds that directory from scratch each time, so it can never drift
# from the source tree.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PUBLIC="${ROOT}/public"

rm -rf "${PUBLIC}"
mkdir -p "${PUBLIC}"

# Frontend assets. static/ is the canonical copy; index.html and app.js at the
# repository root exist for GitHub Pages and must stay byte-identical.
cp "${ROOT}/static/index.html" "${PUBLIC}/index.html"
cp "${ROOT}/static/app.js"     "${PUBLIC}/app.js"
cp "${ROOT}/static/style.css"  "${PUBLIC}/style.css"

# Optional AI panel, copied only if present.
for extra in ai.html ai.js; do
  if [ -f "${ROOT}/static/${extra}" ]; then
    cp "${ROOT}/static/${extra}" "${PUBLIC}/${extra}"
  fi
done

# Map data: required by app.js at boot.
cp -r "${ROOT}/data" "${PUBLIC}/data"

# Runtime API base. Empty keeps the API same-origin by default.
printf 'window.EYEWALL_API_BASE = "%s";\n' "${EYEWALL_API_BASE:-}" > "${PUBLIC}/config.js"

echo "public/ assembled:"
ls -la "${PUBLIC}"
du -sh "${PUBLIC}"
