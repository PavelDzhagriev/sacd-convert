#!/bin/bash
# Ставит зависимости и собирает приложение «Кедр» для macOS.
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Это установщик для macOS. На Linux соберите extractor: scripts/build-sacd-extract.sh" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v brew >/dev/null 2>&1; then
  echo "Нужен Homebrew: https://brew.sh" >&2
  echo "После него снова запустите scripts/install-macos.sh" >&2
  exit 1
fi

brew install cmake libxml2 ffmpeg python

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "Нужен Python 3.9 или новее." >&2
  exit 1
fi

"$ROOT/scripts/build-sacd-extract.sh"
python3 "$ROOT/scripts/make_icon.py"

APP="$ROOT/dist/Kedr.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/kedr" "$APP/Contents/Resources/bin"
cp -R "$ROOT/kedr/." "$APP/Contents/Resources/kedr/"
while IFS= read -r -d '' cached; do
  rm -rf "$cached"
done < <(find "$APP/Contents/Resources/kedr" -type d -name __pycache__ -print0)
cp "$ROOT/bin/sacd_extract" "$APP/Contents/Resources/bin/sacd_extract"
chmod +x "$APP/Contents/Resources/bin/sacd_extract"

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
  <string>1.0.0</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0.0</string>
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
export PYTHONPATH="$APP/Contents/Resources"
export KEDR_RESOURCES="$APP/Contents/Resources"
export KEDR_SACD_EXTRACT="$APP/Contents/Resources/bin/sacd_extract"
cd "$APP/Contents/Resources"
if ! command -v python3 >/dev/null 2>&1; then
  osascript -e 'display alert "Кедр" message "Нужен Python 3.9 или новее. Установите: brew install python"'
  exit 1
fi
if curl -fsS "http://127.0.0.1:47631/api/health" >/dev/null 2>&1; then
  open "http://127.0.0.1:47631"
  exit 0
fi
exec python3 -m kedr serve --open --port 47631
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
