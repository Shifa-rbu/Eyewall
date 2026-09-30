#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
BUILD_DIR="${ROOT}/.hf-space-build"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

ensure_gitignore() {
  local ignore_file="${ROOT}/.gitignore"
  if ! tr -d '\r' < "$ignore_file" | grep -Fxq '.hf-space-build/'; then
    {
      printf '\n# Hugging Face Space payload assembled by deploy/hf-space/push.sh\n'
      printf '.hf-space-build/\n'
    } >> "$ignore_file"
    printf 'Added .hf-space-build/ to .gitignore\n'
  fi
}

check_payload() {
  local payload="$1"
  local source_commit="$2"
  local checks=0

  check() {
    local label="$1"
    shift
    checks=$((checks + 1))
    if "$@"; then
      printf '  PASS %02d %s\n' "$checks" "$label"
    else
      printf '  FAIL %02d %s\n' "$checks" "$label" >&2
      return 1
    fi
  }

  printf 'Checking assembled Space payload (14 checks):\n'
  check 'Dockerfile exists' test -s "${payload}/Dockerfile"
  check 'Space README exists' test -s "${payload}/README.md"
  check 'Docker SDK and exposed Space port are declared' grep -Eq '^sdk: docker$' "${payload}/README.md"
  check 'Space metadata uses port 7860' grep -Eq '^app_port: 7860$' "${payload}/README.md"
  check 'Dockerfile exposes port 7860' grep -Eq '^EXPOSE 7860$' "${payload}/Dockerfile"
  check 'Uvicorn binds all interfaces' grep -Fq -- '--host 0.0.0.0' "${payload}/Dockerfile"
  check 'PORT defaults to 7860' grep -Fq -- '${PORT:-7860}' "${payload}/Dockerfile"
  check 'README records this payload source commit' grep -Fq "$source_commit" "${payload}/README.md"
  check 'Python dependencies are included' test -s "${payload}/requirements.txt"
  check 'FastAPI application source is included' test -s "${payload}/server/main.py"
  check 'Static console files are complete' test -s "${payload}/static/index.html" -a -s "${payload}/static/app.js" -a -s "${payload}/static/style.css" -a -s "${payload}/static/ai.html" -a -s "${payload}/static/ai.js"
  check 'All four map data files are included' test -s "${payload}/data/grid.json" -a -s "${payload}/data/elev.i16" -a -s "${payload}/data/assets.json" -a -s "${payload}/data/tracks.json"
  check 'License is included' test -s "${payload}/LICENSE"
  check 'Card makes no false endpoint or capability claims' bash -c '! grep -Fq "/api/gee/status" "$1" && grep -Fq "/api/health" "$1" && grep -Fq "Earth Engine / Sentinel-1 retrieval is not implemented" "$1" && grep -Fq "population figures" "$1" && grep -Fq "automatic dispatch" "$1" && grep -Fq "returns **403**" "$1"' _ "${payload}/README.md"

  [[ "$checks" -eq 14 ]] || fail "internal check count changed (ran ${checks})"
  printf 'All 14 payload checks passed.\n'
}

assemble() {
  ensure_gitignore

  local source_commit
  source_commit="$(git -C "$ROOT" rev-parse HEAD)"
  git -C "$ROOT" diff --ignore-space-at-eol --quiet HEAD -- Dockerfile requirements.txt server static data LICENSE || \
    fail 'source payload files have uncommitted changes; commit them before assembly'

  case "$BUILD_DIR" in
    "${ROOT}/.hf-space-build") ;;
    *) fail "refusing to replace unexpected payload path: ${BUILD_DIR}" ;;
  esac
  rm -rf -- "$BUILD_DIR"
  mkdir -p "$BUILD_DIR"

  cp "${SCRIPT_DIR}/Dockerfile" "${BUILD_DIR}/Dockerfile"
  sed "s/@SOURCE_COMMIT@/${source_commit}/g" "${SCRIPT_DIR}/README.md" > "${BUILD_DIR}/README.md"
  cp "${ROOT}/requirements.txt" "${BUILD_DIR}/requirements.txt"
  cp "${ROOT}/LICENSE" "${BUILD_DIR}/LICENSE"
  cp -R "${ROOT}/server" "${BUILD_DIR}/server"
  find "${BUILD_DIR}/server" -type d -name '__pycache__' -prune -exec rm -rf -- {} +
  cp -R "${ROOT}/static" "${BUILD_DIR}/static"
  mkdir -p "${BUILD_DIR}/data"
  cp "${ROOT}/data/grid.json" "${BUILD_DIR}/data/grid.json"
  cp "${ROOT}/data/elev.i16" "${BUILD_DIR}/data/elev.i16"
  cp "${ROOT}/data/assets.json" "${BUILD_DIR}/data/assets.json"
  cp "${ROOT}/data/tracks.json" "${BUILD_DIR}/data/tracks.json"

  check_payload "$BUILD_DIR" "$source_commit"
  printf 'Source commit: %s\n' "$source_commit"
  printf 'Payload size: '
  du -sh "$BUILD_DIR" | awk '{print $1}'
  printf 'Payload files: '
  find "$BUILD_DIR" -type f | wc -l | tr -d ' '
  printf '\n'
  if command -v docker >/dev/null 2>&1; then
    printf 'Docker is available; image build is not part of assemble.\n'
  else
    printf 'Docker unavailable; image build has not been verified locally.\n'
  fi
}

push_space() {
  local space_url="${1:-}"
  [[ -n "$space_url" ]] || fail 'usage: push.sh push https://huggingface.co/spaces/<owner>/<space>'
  [[ "$space_url" =~ ^https://huggingface\.co/spaces/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$ ]] || \
    fail 'use the HTTPS URL of a Hugging Face Space repository'
  [[ -d "$BUILD_DIR" ]] || fail 'payload is missing; run push.sh assemble first'

  local source_commit
  source_commit="$(sed -n 's/.*`\([0-9a-f][0-9a-f]*\)`.*/\1/p' "${BUILD_DIR}/README.md" | head -n 1)"
  [[ -n "$source_commit" ]] || fail 'payload README has no source commit record'
  check_payload "$BUILD_DIR" "$source_commit"

  command -v hf >/dev/null 2>&1 || fail 'install the Hugging Face CLI and run `hf auth login` first'
  hf auth whoami >/dev/null 2>&1 || fail 'authenticate with `hf auth login` using a write-enabled token first'

  local publish_dir
  publish_dir="$(mktemp -d "${TMPDIR:-/tmp}/eyewall-hf-push.XXXXXX")"
  [[ "$publish_dir" == "${TMPDIR:-/tmp}"/eyewall-hf-push.* ]] || fail 'unexpected temporary publish path'
  trap 'rm -rf -- "$publish_dir"' EXIT

  git clone "$space_url" "$publish_dir"
  local branch
  branch="$(git -C "$publish_dir" symbolic-ref --short -q HEAD || true)"
  if [[ -z "$branch" ]]; then
    git -C "$publish_dir" checkout -b main
  elif [[ "$branch" != main ]]; then
    if git -C "$publish_dir" show-ref --verify --quiet refs/heads/main; then
      git -C "$publish_dir" checkout main
    else
      git -C "$publish_dir" checkout -b main
    fi
  fi

  cp -R "${BUILD_DIR}/." "$publish_dir/"
  git -C "$publish_dir" config user.name 'Eyewall Space publisher'
  git -C "$publish_dir" config user.email 'eyewall-space-publisher@users.noreply.github.com'
  git -C "$publish_dir" add Dockerfile README.md LICENSE requirements.txt server static data
  if ! git -C "$publish_dir" diff --cached --quiet; then
    git -C "$publish_dir" commit -m "Deploy Eyewall source ${source_commit:0:12}"
  else
    printf 'Space repository already has the assembled payload.\n'
  fi
  git -C "$publish_dir" push origin HEAD:main
  printf 'Pushed source commit %s to %s\n' "$source_commit" "$space_url"
  printf 'Wait for the Space build to finish, then check its runtime logs and /api/health.\n'
}

case "${1:-}" in
  assemble) assemble ;;
  push) push_space "${2:-}" ;;
  *) fail 'usage: push.sh {assemble|push <Space URL>}' ;;
esac
