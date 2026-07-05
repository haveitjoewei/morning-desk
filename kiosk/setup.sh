#!/bin/bash
# One-time kiosk setup for the Morning Desk dashboard on macOS.
# Runs the fullscreen dashboard twice a day (morning + evening), waking from sleep.
# Run ON THE LAPTOP you want as the display:   bash kiosk/setup.sh
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER="$HERE/morning-kiosk.sh"
BASE="https://morning-desk-ashen.vercel.app"
MORNING="06:30"          # HH:MM (24h) wake #1
EVENING="22:00"          # HH:MM (24h) wake #2  (10pm)
LABEL="com.morningdesk.kiosk"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
USER_NAME="$(id -un)"

MH=${MORNING%:*}; MM=${MORNING#*:}
EH=${EVENING%:*}; EM=${EVENING#*:}
MRUN=$((10#$MM + 1)); ERUN=$((10#$EM + 1))   # launchd fires 1 min after wake

echo "Morning Desk kiosk — waking $MORNING and $EVENING daily."

# 0. Let this user run pmset without a password, so the schedule can re-arm itself.
echo "Configuring power scheduling (needs your Mac password once)…"
echo "$USER_NAME ALL=(root) NOPASSWD: /usr/bin/pmset" | sudo tee /etc/sudoers.d/morningdesk >/dev/null
sudo chmod 440 /etc/sudoers.d/morningdesk

# 1. Mint a long-lived no-PIN token + generate the launcher (only if missing).
if [ ! -f "$LAUNCHER" ]; then
  printf "Your Morning Desk PIN (Joseph): "; read -rs PIN; echo
  RESP="$(curl -s -X POST "$BASE/api/unlock" -H 'Content-Type: application/json' -d "{\"pin\":\"$PIN\",\"kiosk\":true}")"
  TOKEN="$(printf '%s' "$RESP" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')"
  [ -z "$TOKEN" ] && { echo "Couldn't mint a token — wrong PIN?"; exit 1; }
  cat > "$LAUNCHER" <<LAUNCHEOF
#!/bin/bash
# Morning Desk kiosk launcher (auto-generated; contains a device token — keep private).
URL="$BASE/dashboard?k=$TOKEN"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# Re-arm the NEXT wake so the other run fires even from deep sleep.
H=\$(date +%H)
if [ "\$H" -lt 12 ]; then
  sudo /usr/bin/pmset schedule wake "\$(date -v${EH}H -v${EM}M -v0S '+%m/%d/%y %H:%M:%S')" 2>/dev/null || true
else
  sudo /usr/bin/pmset schedule wake "\$(date -v+1d -v${MH}H -v${MM}M -v0S '+%m/%d/%y %H:%M:%S')" 2>/dev/null || true
fi
pkill -f "morningdesk-kiosk" 2>/dev/null || true      # avoid stacking windows
/usr/bin/caffeinate -d -t 7200 &                      # hold the screen awake 2h
"\$CHROME" --kiosk --app="\$URL" --user-data-dir="\$HOME/.morningdesk-kiosk" \\
  --no-first-run --no-default-browser-check --disable-translate \\
  --disable-features=TranslateUI --overscroll-history-navigation=0 \\
  --disable-session-crashed-bubble --disable-infobars >/dev/null 2>&1 &
LAUNCHEOF
  chmod +x "$LAUNCHER"
  echo "  ✓ launcher written."
fi

# 2. Baseline repeating morning wake (safety net if the re-arm chain ever breaks).
sudo pmset repeat wakeorpoweron MTWRFSU "${MORNING}:00"

# 3. Arm the next upcoming wake right now (tonight's evening).
sudo pmset schedule wake "$(date -v${EH}H -v${EM}M -v0S '+%m/%d/%y %H:%M:%S')" 2>/dev/null || true

# 4. Launch agent that opens the kiosk at both times (fires on wake if asleep).
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$LAUNCHER</string></array>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Hour</key><integer>$((10#$MH))</integer><key>Minute</key><integer>$MRUN</integer></dict>
    <dict><key>Hour</key><integer>$((10#$EH))</integer><key>Minute</key><integer>$ERUN</integer></dict>
  </array>
  <key>RunAtLoad</key><false/>
</dict></plist>
PLISTEOF
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo
echo "Done. Wakes $MORNING and $EVENING, opens the dashboard fullscreen a minute later."
echo "  • Test the display now:   bash kiosk/morning-kiosk.sh   (Cmd+Q to quit)"
echo "  • Rehearse wake-from-sleep: bash kiosk/rehearse.sh"
echo "  • Undo everything:        bash kiosk/uninstall.sh"
echo "  • Needs Google Chrome installed."
