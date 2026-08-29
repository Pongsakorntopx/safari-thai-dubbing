#!/bin/bash
set -e

# Safari Web Extension Converter Helper Script
EXTENSION_DIR="./extension"
XCODE_DIR="./xcode-wrapper"
APP_NAME="Thai Dubbing for Safari"

# Auto-detect Xcode Developer directory if not set
if [ -z "$DEVELOPER_DIR" ]; then
    if [ -d "/Applications/Xcode.app/Contents/Developer" ]; then
        export DEVELOPER_DIR="/Applications/Xcode.app/Contents/Developer"
    elif [ -d "$HOME/Downloads/Xcode-beta.app/Contents/Developer" ]; then
        export DEVELOPER_DIR="$HOME/Downloads/Xcode-beta.app/Contents/Developer"
    elif [ -d "/Applications/Xcode-beta.app/Contents/Developer" ]; then
        export DEVELOPER_DIR="/Applications/Xcode-beta.app/Contents/Developer"
    fi
fi

echo "========================================================"
echo " Converting Web Extension to Safari Xcode Project..."
echo " Using Developer Dir: $DEVELOPER_DIR"
echo "========================================================"

mkdir -p "$XCODE_DIR"

xcrun safari-web-extension-converter "$EXTENSION_DIR" \
    --project-location "$XCODE_DIR" \
    --app-name "$APP_NAME" \
    --swift \
    --macos-only \
    --no-open \
    --force

echo "========================================================"
echo " Conversion complete!"
echo " Xcode project generated in: $XCODE_DIR"
echo ""
echo " Next Steps to run in Safari:"
echo " 1. Open the project in Xcode:"
echo "    open '$XCODE_DIR/$APP_NAME/$APP_NAME.xcodeproj'"
echo " 2. In Xcode, select 'Thai Dubbing for Safari (macOS)' scheme."
echo " 3. Click Run (Cmd + R) to build and install the host app."
echo " 4. In Safari -> Settings -> Advanced, check 'Show features for web developers'."
echo " 5. In Safari Developer menu, check 'Allow Unsigned Extensions'."
echo " 6. In Safari -> Settings -> Extensions, enable 'Thai Dubbing for Safari'."
echo "========================================================"
