#!/bin/bash
# Ставит зависимости и собирает приложение «Кедр» для macOS.
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Это установщик для macOS." >&2
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
      echo "На Windows: powershell -ExecutionPolicy Bypass -File scripts/install-windows.ps1" >&2
      ;;
    *)
      echo "На Linux соберите extractor: scripts/build-sacd-extract.sh" >&2
      ;;
  esac
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v brew >/dev/null 2>&1; then
  echo "Нужен Homebrew: https://brew.sh" >&2
  echo "После него снова запустите scripts/install-macos.sh" >&2
  exit 1
fi

brew install cmake pkgconf libxml2 ffmpeg python node

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "Нужен Python 3.9 или новее." >&2
  exit 1
fi

"$ROOT/scripts/build-sacd-extract.sh"
python3 "$ROOT/scripts/make_icon.py"
(cd "$ROOT" && npm install)

APP="$ROOT/dist/Kedr.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>Кедр</string>
  <key>CFBundleDisplayName</key>
  <string>Кедр</string>
  <key>CFBundleIdentifier</key>
  <string>local.kedr.dsdflac</string>
  <key>CFBundleVersion</key>
  <string>1.1.0</string>
  <key>CFBundleShortVersionString</key>
  <string>1.1.0</string>
  <key>CFBundleExecutable</key>
  <string>kedr</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>LSApplicationCategoryType</key>
  <string>public.app-category.music</string>
</dict>
</plist>
PLIST

cat > "$APP/Contents/MacOS/kedr" << EOF
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:\$PATH"
export PYTHONPATH="$ROOT"
export KEDR_SACD_EXTRACT="$ROOT/bin/sacd_extract"
cd "$ROOT"
ELECTRON="$ROOT/node_modules/.bin/electron"
if [[ ! -x "\$ELECTRON" ]]; then
  osascript -e 'display alert "Кедр" message "Не найден Electron. В папке проекта выполните: npm install"'
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  osascript -e 'display alert "Кедр" message "Нужен Python 3.9 или новее. Установите: brew install python"'
  exit 1
fi
exec "\$ELECTRON" "$ROOT"
EOF
chmod +x "$APP/Contents/MacOS/kedr"

if command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
  ICONSET="$ROOT/build/AppIcon.iconset"
  rm -rf "$ICONSET"
  mkdir -p "$ICONSET"
  for size in 16 32 128 256 512; do
    sips -z "$size" "$size" "$ROOT/kedr/web/icon.png" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
    double=$((size * 2))
    if [[ "$double" -le 512 ]]; then
      sips -z "$double" "$double" "$ROOT/kedr/web/icon.png" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
    fi
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"
fi

mkdir -p "$HOME/Applications"
ln -sfn "$APP" "$HOME/Applications/Kedr.app"
echo "Готово. Откройте «Кедр» из ~/Applications или командой: open \"$APP\""
