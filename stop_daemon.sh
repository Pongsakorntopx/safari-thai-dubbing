#!/usr/bin/env bash
# Safari Thai Dubbing - Stop Background Daemon
PLIST_PATH="$HOME/Library/LaunchAgents/com.thaidubbing.backend.plist"

if [ -f "$PLIST_PATH" ]; then
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    echo "🛑 Thai Dubbing Backend daemon stopped."
else
    echo "ℹ️ No daemon plist found."
fi
