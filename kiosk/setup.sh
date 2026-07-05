#!/bin/bash
# One-time kiosk setup for the Morning Desk dashboard on macOS.
# Run this ON THE LAPTOP you want as the morning display:  bash kiosk/setup.sh
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER="$HERE/morning-kiosk.sh"
BASE="https://morning-desk-ashen.vercel.app"
WAKE_HHMM="06:30:00"          # when the Mac wakes
RUN_HOUR=6; RUN_MIN=31        # when the dashboard opens (a minute after wake)
LABEL="com.morningdesk.kiosk"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

# 1. Mint a long-lived, no-PIN token for this device (asks for your dashboard PIN once).
if [ ! -f "$LAUNCHER" ]; then
  echo "Your Morning Desk PIN (Joseph):"
  read -rs PIN; echo
  echo "Minting a kiosk token…"
  RESP="$(curl -s -X POST "$BASE/api/unlock" -H 'Content-Type: application/json' -d "{\"pin\":\"$PIN\",\"kiosk\":true}")"
  TOKEN="$(printf '%s' "$RESP" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')"
  if [ -z "$TOKEN" ]; then echo "Couldn't mint a token — wrong PIN?"; exit 1; fi
  cat > "$LAUNCHER" <<LAUNCHEOF
#!/bin/bash
# Morning Desk kiosk launcher (auto-generated). Contains a bearer token for this
# device — keep private. Regenerate by deleting this file and re-running setup.sh.
URL="$BASE/dashboard?k=$TOKEN"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
/usr/bin/caffeinate -d -t 10800 &
"\$CHROME" --kiosk --app="\$URL" --user-data-dir="\$HOME/.morningdesk-kiosk" \\
  --no-first-run --no-default-browser-check --disable-translate \\
  --disable-features=TranslateUI --overscroll-history-navigation=0 \\
  --disable-session-crashed-bubble --disable-infobars >/dev/null 2>&1 &
LAUNCHEOF
  chmod +x "$LAUNCHER"
  echo "  ✓ launcher written."
fi

# 2. Wake the Mac every day.
echo "Scheduling daily wake at ${WAKE_HHMM} (needs your Mac password)…"
sudo pmset repeat wakeorpoweron MTWRFSU "$WAKE_HHMM"

# 3. Launch agent that opens the kiosk a minute after wake.
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$LAUNCHER</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>$RUN_HOUR</integer><key>Minute</key><integer>$RUN_MIN</integer></dict>
  <key>RunAtLoad</key><false/>
</dict></plist>
PLISTEOF
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo
echo "Done. Mac wakes ${WAKE_HHMM}, dashboard opens ${RUN_HOUR}:${RUN_MIN} fullscreen."
echo "  • Test now:     bash kiosk/morning-kiosk.sh   (Cmd+Q to quit)"
echo "  • Undo:         launchctl unload \"$PLIST\" && sudo pmset repeat cancel"
echo "  • Needs Google Chrome installed."
