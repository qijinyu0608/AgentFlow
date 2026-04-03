#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
MAC_DIST_DIR="$ROOT_DIR/dist-macos"
APP_NAME="AgentMesh"
APP_BUNDLE="$MAC_DIST_DIR/${APP_NAME}.app"
APP_CONTENTS="$APP_BUNDLE/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_RESOURCES="$APP_CONTENTS/Resources"
APP_PAYLOAD="$APP_RESOURCES/app"
ZIP_PATH="$MAC_DIST_DIR/${APP_NAME}-macOS.zip"

cd "$ROOT_DIR"

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

echo "[1/5] Building frontend..."
cd "$ROOT_DIR/frontend"
npm install
npm run build
cd "$ROOT_DIR"

echo "[2/5] Installing PyInstaller..."
"$PYTHON_BIN" -m pip install pyinstaller

echo "[3/5] Packaging runtime with PyInstaller..."
"$PYTHON_BIN" -m PyInstaller --noconfirm --clean agentmesh.spec

echo "[4/5] Creating macOS app bundle..."
rm -rf "$APP_BUNDLE"
mkdir -p "$APP_MACOS" "$APP_RESOURCES"
cp -R "$DIST_DIR/$APP_NAME" "$APP_PAYLOAD"

if [[ -f "$ROOT_DIR/config-template.yaml" ]]; then
  cp "$ROOT_DIR/config-template.yaml" "$APP_PAYLOAD/config-template.yaml"
fi
if [[ -f "$ROOT_DIR/config.yaml" ]]; then
  cp "$ROOT_DIR/config.yaml" "$APP_PAYLOAD/config.yaml"
fi
if [[ -d "$ROOT_DIR/data" ]]; then
  rm -rf "$APP_PAYLOAD/data"
  cp -R "$ROOT_DIR/data" "$APP_PAYLOAD/data"
fi

cat > "$APP_MACOS/$APP_NAME" <<'EOF'
#!/bin/zsh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/../Resources/app" && pwd)"
cd "$APP_DIR"
exec "$APP_DIR/AgentMesh" "$@"
EOF
chmod +x "$APP_MACOS/$APP_NAME"

cat > "$APP_CONTENTS/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleDisplayName</key>
  <string>AgentMesh</string>
  <key>CFBundleExecutable</key>
  <string>AgentMesh</string>
  <key>CFBundleIdentifier</key>
  <string>com.agentmesh.desktop</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>AgentMesh</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOF

echo "[5/5] Creating zip archive..."
rm -f "$ZIP_PATH"
mkdir -p "$MAC_DIST_DIR"
ditto -c -k --sequesterRsrc --keepParent "$APP_BUNDLE" "$ZIP_PATH"

echo
echo "Packaging complete."
echo "App bundle: $APP_BUNDLE"
echo "Zip archive: $ZIP_PATH"
