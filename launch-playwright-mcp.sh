#!/bin/bash
# Playwright MCP Wrapper — erstellt pro Session ein isoliertes Browser-Profil.
# Ermöglicht mehrere parallele Claude-Code-Instanzen ohne Konflikte.

TMPDIR=$(mktemp -d /tmp/playwright-mcp-XXXXXX)

cat > "$TMPDIR/config.json" <<EOF
{
  "browser": {
    "userDataDir": "$TMPDIR/profile",
    "browserName": "chromium",
    "launchOptions": {
      "args": [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check"
      ]
    },
    "contextOptions": {
      "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
      "viewport": { "width": 1920, "height": 1080 }
    }
  }
}
EOF

trap "rm -rf $TMPDIR" EXIT

exec npx @playwright/mcp@latest --config="$TMPDIR/config.json"
