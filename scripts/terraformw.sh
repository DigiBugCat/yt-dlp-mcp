#!/usr/bin/env bash
set -euo pipefail

# Simple terraform wrapper:
# - Downloads a known-good terraform version into .tools/terraform if missing
# - Executes it with provided args

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_DIR="$ROOT_DIR/.tools"
TF_BIN="$TOOLS_DIR/terraform"
TF_VERSION="1.14.4"

os="$(uname -s | tr '[:upper:]' '[:lower:]')"
arch="$(uname -m)"

case "$arch" in
  x86_64|amd64) arch="amd64" ;;
  arm64|aarch64) arch="arm64" ;;
  *)
    echo "Unsupported arch: $arch" >&2
    exit 2
    ;;
esac

case "$os" in
  darwin|linux) ;;
  *)
    echo "Unsupported OS: $os" >&2
    exit 2
    ;;
esac

ensure_terraform() {
  if [[ -x "$TF_BIN" ]]; then
    # Replace if version doesn't match.
    if "$TF_BIN" version 2>/dev/null | head -n1 | rg -q "Terraform v${TF_VERSION}"; then
      return 0
    fi
  fi

  mkdir -p "$TOOLS_DIR"

  zip_name="terraform_${TF_VERSION}_${os}_${arch}.zip"
  url="https://releases.hashicorp.com/terraform/${TF_VERSION}/${zip_name}"

  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' EXIT

  echo "Downloading terraform ${TF_VERSION} (${os}/${arch})..." >&2
  curl -fsSL "$url" -o "$tmpdir/$zip_name"

  if command -v unzip >/dev/null 2>&1; then
    unzip -q "$tmpdir/$zip_name" -d "$tmpdir"
  else
    python3 - <<PY
import zipfile
with zipfile.ZipFile("$tmpdir/$zip_name") as z:
    z.extractall("$tmpdir")
PY
  fi

  install -m 0755 "$tmpdir/terraform" "$TF_BIN"
}

ensure_terraform
exec "$TF_BIN" "$@"
