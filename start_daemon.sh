#!/usr/bin/env bash
# Safari Thai Dubbing - Background Daemon Manager (LaunchAgent)
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLIST_PATH="$HOME/Library/LaunchAgents/com.thaidubbing.backend.plist"

cat <<EOF > "$PLIST_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.thaidubbing.backend</string>
    <key>ProgramArguments</key>
    <array>
        <string>${DIR}/backend/venv/bin/python3</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>app.main:app</string>
        <string>--host</string>
        <string>127.0.0.1</string>
        <string>--port</string>
        <string>8000</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${DIR}/backend</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>${DIR}/backend</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/thai_dubbing_backend.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/thai_dubbing_backend_err.log</string>
</dict>
</plist>
EOF

# Unload previous instance if loaded
launchctl unload "$PLIST_PATH" 2>/dev/null || true
# Load and start daemon
launchctl load "$PLIST_PATH"

echo "✅ Thai Dubbing Backend daemon successfully started in background!"
echo "🌐 Local endpoint: http://127.0.0.1:8000"
echo "📄 Logs: /tmp/thai_dubbing_backend.log"
