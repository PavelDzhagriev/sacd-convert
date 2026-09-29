#!/bin/bash
# Собирает sacd_extract — единственный надёжный способ прочитать SACD ISO.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIN="a3d981c935c3224217e2842cd492f9351106c81e"
SRC="$ROOT/build/sacd-ripper"
BUILD="$ROOT/build/sacd-extract"

if [[ -d /opt/homebrew ]]; then
  export PATH="/opt/homebrew/bin:$PATH"
  prefix="$(/opt/homebrew/bin/brew --prefix libxml2 2>/dev/null || true)"
  if [[ -n "${prefix}" ]]; then
    export PKG_CONFIG_PATH="${prefix}/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
    export CPPFLAGS="-I${prefix}/include ${CPPFLAGS:-}"
    export LDFLAGS="-L${prefix}/lib ${LDFLAGS:-}"
  fi
fi

if ! command -v cmake >/dev/null 2>&1; then
  echo "Нужен cmake. На Mac: brew install cmake libxml2" >&2
  exit 1
fi
if ! command -v pkg-config >/dev/null 2>&1 || ! pkg-config --exists libxml-2.0; then
  echo "Нужна libxml2 с заголовками. На Mac: brew install libxml2" >&2
  exit 1
fi

mkdir -p "$ROOT/build" "$ROOT/bin"
if [[ ! -d "$SRC/.git" ]]; then
  rm -rf "$SRC"
  GIT_TERMINAL_PROMPT=0 git clone --depth 1 https://github.com/sacd-ripper/sacd-ripper.git "$SRC"
fi
git -C "$SRC" fetch --depth 1 origin "$PIN"
git -C "$SRC" checkout --detach "$PIN"

python3 - "$SRC/tools/sacd_extract/CMakeLists.txt" << 'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text()
old = 'if(NOT CMAKE_HOST_SYSTEM_PROCESSOR MATCHES "arm*")'
new = 'if(NOT CMAKE_HOST_SYSTEM_PROCESSOR MATCHES "arm*" AND NOT CMAKE_HOST_SYSTEM_PROCESSOR MATCHES "aarch64")'
if old in text and new not in text:
    path.write_text(text.replace(old, new, 1))
PY

cmake -S "$SRC/tools/sacd_extract" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD" -j"$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)"
cp "$BUILD/sacd_extract" "$ROOT/bin/sacd_extract"
chmod +x "$ROOT/bin/sacd_extract"
echo "Готово: $ROOT/bin/sacd_extract"
