#!/bin/bash
# Собирает sacd_extract — единственный надёжный способ прочитать SACD ISO.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIN="a3d981c935c3224217e2842cd492f9351106c81e"

copy_runtime_dlls() {
  local exe="$1" dest="$2"
  if ! command -v ldd >/dev/null 2>&1; then
    echo "ldd не найден, DLL рядом с sacd_extract.exe не скопированы." >&2
    return 0
  fi
  local deps=""
  deps="$(ldd "$exe" 2>/dev/null || true)"
  local line target
  while IFS= read -r line; do
    case "$line" in
      *"=>"*) ;;
      *) continue ;;
    esac
    target="${line#*=> }"
    target="${target%% (*}"
    target="${target%"${target##*[![:space:]]}"}"
    case "$target" in
      /ucrt64/*|/mingw64/*|/mingw32/*|/usr/*)
        cp -f "$target" "$dest/"
        ;;
    esac
  done <<< "$deps"
}

SRC="$ROOT/build/sacd-ripper"
BUILD="$ROOT/build/sacd-extract"

# Homebrew держит libxml2 как keg-only: заголовки не в /usr/include, а pkg-config
# ставится отдельной формулой pkgconf. Ищем и Apple Silicon, и Intel.
LIBXML_CFLAGS=""
LIBXML_LDFLAGS=""
brew_bin=""
if command -v brew >/dev/null 2>&1; then
  brew_bin="$(command -v brew)"
elif [[ -x /opt/homebrew/bin/brew ]]; then
  brew_bin=/opt/homebrew/bin/brew
elif [[ -x /usr/local/bin/brew ]]; then
  brew_bin=/usr/local/bin/brew
fi
if [[ -n "$brew_bin" ]]; then
  brew_prefix="$("$brew_bin" --prefix)"
  export PATH="${brew_prefix}/bin:${PATH}"
  xml_prefix="$("$brew_bin" --prefix libxml2 2>/dev/null || true)"
  if [[ -n "$xml_prefix" && -d "$xml_prefix/include/libxml2" ]]; then
    export PATH="${xml_prefix}/bin:${PATH}"
    export PKG_CONFIG_PATH="${xml_prefix}/lib/pkgconfig${PKG_CONFIG_PATH:+:${PKG_CONFIG_PATH}}"
    export CMAKE_PREFIX_PATH="${xml_prefix}${CMAKE_PREFIX_PATH:+:${CMAKE_PREFIX_PATH}}"
    LIBXML_CFLAGS="-I${xml_prefix}/include/libxml2 -I${xml_prefix}/include"
    LIBXML_LDFLAGS="-L${xml_prefix}/lib"
    export CPPFLAGS="${LIBXML_CFLAGS} ${CPPFLAGS:-}"
    export CFLAGS="${LIBXML_CFLAGS} ${CFLAGS:-}"
    export LDFLAGS="${LIBXML_LDFLAGS} ${LDFLAGS:-}"
    echo "libxml2: ${xml_prefix}"
  fi
fi

if ! command -v cmake >/dev/null 2>&1; then
  echo "Нужен cmake. На Mac: brew install cmake libxml2 pkgconf" >&2
  exit 1
fi
have_libxml=0
if [[ -n "$LIBXML_CFLAGS" ]] || command -v xml2-config >/dev/null 2>&1; then
  have_libxml=1
elif command -v pkg-config >/dev/null 2>&1 && pkg-config --exists libxml-2.0; then
  have_libxml=1
fi
if [[ "$have_libxml" -ne 1 ]]; then
  echo "Нужна libxml2 с заголовками. На Mac: brew install libxml2 pkgconf" >&2
  echo "Это keg-only формула: заголовки в \$(brew --prefix libxml2)/include/libxml2, не в /usr/include." >&2
  exit 1
fi

mkdir -p "$ROOT/build" "$ROOT/bin"
if [[ ! -d "$SRC/.git" ]]; then
  rm -rf "$SRC"
  GIT_TERMINAL_PROMPT=0 git clone --depth 1 https://github.com/sacd-ripper/sacd-ripper.git "$SRC"
fi
git -C "$SRC" fetch --depth 1 origin "$PIN"
git -C "$SRC" checkout --force --detach "$PIN"

PYTHON="$(command -v python3 || command -v python || true)"
if [[ -z "$PYTHON" ]]; then
  echo "Нужен python3." >&2
  exit 1
fi

"$PYTHON" - "$SRC/tools/sacd_extract/CMakeLists.txt" << 'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text()
old = 'if(NOT CMAKE_HOST_SYSTEM_PROCESSOR MATCHES "arm*")'
new = 'if(NOT CMAKE_HOST_SYSTEM_PROCESSOR MATCHES "arm*" AND NOT CMAKE_HOST_SYSTEM_PROCESSOR MATCHES "aarch64")'
if old in text and new not in text:
    text = text.replace(old, new, 1)
# Обратные кавычки здесь не запускают xml2-config, а Clang на Mac падает на --cflags.
text = text.replace(" `xml2-config --cflags --libs`", "")
# -static тянет все зависимости libxml2 статически и на MSYS2 обычно не линкуется.
text = text.replace(" -lxml2 -static", " -lxml2")
needle = "find_package(LibXml2 REQUIRED)\n"
include = "include_directories(${LIBXML2_INCLUDE_DIR})\n"
if needle in text and include not in text:
    text = text.replace(needle, needle + include, 1)
path.write_text(text)
PY

rm -rf "$BUILD"
cmake_args=(
  -S "$SRC/tools/sacd_extract"
  -B "$BUILD"
  -DCMAKE_BUILD_TYPE=Release
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5
)
if [[ -n "$LIBXML_CFLAGS" ]]; then
  cmake_args+=("-DCMAKE_C_FLAGS=${LIBXML_CFLAGS}")
  cmake_args+=("-DCMAKE_EXE_LINKER_FLAGS=${LIBXML_LDFLAGS}")
fi
cmake "${cmake_args[@]}"
cmake --build "$BUILD" -j"$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || echo 4)"

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    BIN_NAME="sacd_extract.exe"
    ;;
  *)
    BIN_NAME="sacd_extract"
    ;;
esac
artifact="$BUILD/$BIN_NAME"
if [[ ! -f "$artifact" ]]; then
  artifact="$(find "$BUILD" -type f -name "$BIN_NAME" -print -quit)"
fi
if [[ -z "${artifact}" || ! -f "$artifact" ]]; then
  echo "Сборка не создала $BIN_NAME." >&2
  exit 1
fi
cp "$artifact" "$ROOT/bin/$BIN_NAME"
chmod +x "$ROOT/bin/$BIN_NAME"
if [[ "$BIN_NAME" == "sacd_extract.exe" ]]; then
  copy_runtime_dlls "$ROOT/bin/$BIN_NAME" "$ROOT/bin"
fi
echo "Готово: $ROOT/bin/$BIN_NAME"
