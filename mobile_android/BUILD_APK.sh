#!/usr/bin/env bash
#
# NamVibe Android APK Build Script
# =================================
# Builds the Capacitor Android wrapper for the NamVibe Flask app.
#
# Prerequisites:
#   - Java JDK 17+
#   - Android SDK (API 34+)
#   - Node.js 20+
#   - Running NamVibe Flask backend (or configure URL in capacitor.config.json)
#
# Environment variables:
#   ANDROID_HOME    - Path to Android SDK (e.g., ~/Library/Android/sdk)
#   JAVA_HOME       - Path to JDK (e.g., /usr/lib/jvm/java-17-openjdk)
#   NAMVIBE_URL     - Flask backend URL (default: http://192.168.179.30:5000)
#
# Usage:
#   ./BUILD_APK.sh [debug|release]
#
# Output:
#   mobile_android/android/app/build/outputs/apk/debug/app-debug.apk
#   mobile_android/android/app/build/outputs/apk/release/app-release-unsigned.apk

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

BUILD_TYPE="${1:-debug}"

# --- Check prerequisites ---
echo "==> Checking prerequisites..."

if ! command -v node &>/dev/null; then
    echo "ERROR: Node.js not found. Install Node.js 20+."
    exit 1
fi

if ! command -v java &>/dev/null; then
    echo "ERROR: Java not found. Install JDK 17+."
    exit 1
fi

if [ -z "${ANDROID_HOME:-}" ]; then
    if [ -d "$HOME/Library/Android/sdk" ]; then
        export ANDROID_HOME="$HOME/Library/Android/sdk"
        echo "    ANDROID_HOME=$ANDROID_HOME"
    elif [ -d "$HOME/Android/Sdk" ]; then
        export ANDROID_HOME="$HOME/Android/Sdk"
        echo "    ANDROID_HOME=$ANDROID_HOME"
    else
        echo "ERROR: ANDROID_HOME not set and Android SDK not found in default locations."
        exit 1
    fi
fi

if [ -z "${JAVA_HOME:-}" ]; then
    # Try to locate JDK
    if [ -d "/usr/lib/jvm/java-17-openjdk" ]; then
        export JAVA_HOME="/usr/lib/jvm/java-17-openjdk"
    elif [ -d "/usr/lib/jvm/java-11-openjdk" ]; then
        export JAVA_HOME="/usr/lib/jvm/java-11-openjdk"
    elif [ -d "/Applications/Android Studio.app/Contents/jbr/Contents/Home" ]; then
        export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
    else
        echo "WARNING: JAVA_HOME not set. Attempting build with default java."
    fi
fi

export PATH="$ANDROID_HOME/tools:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"

# --- Configure Flask backend URL ---
if [ -n "${NAMVIBE_URL:-}" ]; then
    echo "==> Setting Flask backend URL to: $NAMVIBE_URL"
    # Update capacitor.config.json with the provided URL
    TMP_FILE=$(mktemp)
    node -e "
        const cfg = require('./capacitor.config.json');
        cfg.server.url = '$NAMVIBE_URL';
        cfg.server.allowNavigation = ['$(echo "$NAMVIBE_URL" | sed 's|http[s]*://||' | sed 's|/.*$||'):*'];
        require('fs').writeFileSync('$TMP_FILE', JSON.stringify(cfg, null, 2) + '\n');
    " && mv "$TMP_FILE" capacitor.config.json
fi

# --- Install npm dependencies ---
echo "==> Installing npm dependencies..."
npm install --silent

# --- Sync Capacitor with Android project ---
echo "==> Syncing Capacitor with Android project..."
npx cap sync android

# --- Build APK ---
echo "==> Building APK ($BUILD_TYPE)..."
cd android

if [ "$BUILD_TYPE" = "release" ]; then
    ./gradlew assembleRelease
    APK_PATH="app/build/outputs/apk/release/app-release-unsigned.apk"
    echo ""
    echo "======================================================"
    echo "  RELEASE APK (unsigned) built:"
    echo "    $SCRIPT_DIR/android/$APK_PATH"
    echo ""
    echo "  To sign the release APK:"
    echo "    jarsigner -keystore your-key.keystore \\"
    echo "      $SCRIPT_DIR/android/$APK_PATH namvibe"
    echo "    zipalign -v 4 $SCRIPT_DIR/android/$APK_PATH NamVibe-release.apk"
    echo "======================================================"
else
    ./gradlew assembleDebug
    APK_PATH="app/build/outputs/apk/debug/app-debug.apk"
    echo ""
    echo "======================================================"
    echo "  DEBUG APK built:"
    echo "    $SCRIPT_DIR/android/$APK_PATH"
    echo "======================================================"
fi
