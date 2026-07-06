#!/bin/bash
# One-time kiosk setup for the Morning Desk dashboard on a PERSONAL Mac.
# The kiosk pops up fullscreen only at the scheduled times (morning + evening);
# the rest of the day it's your normal desktop. Cmd+Q dismisses it.
#   bash kiosk/setup.sh
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER="$HERE/morning-kiosk.sh"
BASE="https://morning-desk-ashen.vercel.app"
MORNING="06:30"          # HH:MM (24h)
EVENING="22:00"          # HH:MM (24h)  (10pm)
UID_NUM="$(id -u)"; USER_NAME="$(id -un)"
LA="$HOME/Library/LaunchAgents"
PLIST="$LA/com.morningdesk.kiosk.plist"
LOG="$HOME/Library/Logs/morningdesk-kiosk.log"

MH=${MORNING%:*}; MM=${MORNING#*:}; EH=${EVENING%:*}; EM=${EVENING#*:}
mkdir -p "$LA" "$HOME/Library/Logs"
echo "Morning Desk kiosk — pops up at $MORNING and $EVENING, otherwise your normal desktop."

# 0. Passwordless pmset so the schedule can re-arm itself each run.
echo "Configuring (needs your Mac password once)…"
echo "$USER_NAME ALL=(root) NOPASSWD: /usr/bin/pmset" | sudo tee /etc/sudoers.d/morningdesk >/dev/null
sudo chmod 440 /etc/sudoers.d/morningdesk

# 0b. Don't require a password on the scheduled wake, or the kiosk hides behind the
# lock screen. (Your normal manual wakes are unaffected by the schedule.)
echo "Turning off the wake password (enter your Mac LOGIN password):"
sysadminctl -screenLock off -password - 2>/dev/null || \
  echo "  ! set manually: Lock Screen → 'Require password' → Never."

# 1. Mint a no-PIN token + write the launcher (launches Chrome kiosk, then exits).
if [ ! -f "$LAUNCHER" ]; then
  printf "Your Morning Desk PIN (Joseph): "; read -rs PIN; echo
  RESP="$(curl -s -X POST "$BASE/api/unlock" -H 'Content-Type: application/json' -d "{\"pin\":\"$PIN\",\"kiosk\":true}")"
  TOKEN="$(printf '%s' "$RESP" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')"
  [ -z "$TOKEN" ] && { echo "Wrong PIN?"; exit 1; }
  cat > "$LAUNCHER" <<LAUNCHEOF
#!/bin/bash
# Morning Desk kiosk launcher (auto-generated; token inside — keep private).
URL="$BASE/dashboard?k=$TOKEN"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
LOG="$LOG"
echo "\$(date '+%F %T') launcher fired" >> "\$LOG"
/usr/bin/caffeinate -u -t 3 >/dev/null 2>&1 &        # wake the display
# Re-arm the other wake so it fires from sleep.
H=\$(date +%H)
if [ "\$H" -lt 12 ]; then
  sudo /usr/bin/pmset schedule wakeorpoweron "\$(date -v${EH}H -v${EM}M -v0S '+%m/%d/%y %H:%M:%S')" >>"\$LOG" 2>&1 || true
else
  sudo /usr/bin/pmset schedule wakeorpoweron "\$(date -v+1d -v${MH}H -v${MM}M -v0S '+%m/%d/%y %H:%M:%S')" >>"\$LOG" 2>&1 || true
fi
# Open the kiosk (skip if one is already up).
if ! pgrep -f "morningdesk-kiosk" >/dev/null; then
  "\$CHROME" --kiosk --app="\$URL" --user-data-dir="\$HOME/.morningdesk-kiosk" \\
    --no-first-run --no-default-browser-check --disable-translate \\
    --disable-features=TranslateUI --overscroll-history-navigation=0 \\
    --disable-session-crashed-bubble --disable-infobars >>"\$LOG" 2>&1 &
  echo "\$(date '+%F %T') chrome launched" >> "\$LOG"
fi
LAUNCHEOF
  chmod +x "$LAUNCHER"
  echo "  ✓ launcher written."
fi

# 2. Wakes: repeating morning + arm tonight's evening now.
sudo pmset repeat wakeorpoweron MTWRFSU "${MORNING}:00"
sudo pmset schedule wakeorpoweron "$(date -v${EH}H -v${EM}M -v0S '+%m/%d/%y %H:%M:%S')" 2>/dev/null || true

# 3. Agent that opens the kiosk at both times (fires on wake). No KeepAlive — you
#    Cmd+Q to dismiss and get back to work.
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.morningdesk.kiosk</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$LAUNCHER</string></array>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Hour</key><integer>$((10#$MH))</integer><key>Minute</key><integer>$((10#$MM + 1))</integer></dict>
    <dict><key>Hour</key><integer>$((10#$EH))</integer><key>Minute</key><integer>$((10#$EM + 1))</integer></dict>
  </array>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict></plist>
PLISTEOF

# 4. Load with the modern API (launchctl load is unreliable on recent macOS).
launchctl bootout "gui/$UID_NUM" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$UID_NUM" "$PLIST"

echo
echo "Done. Kiosk pops up at $MORNING and $EVENING; Cmd+Q to dismiss."
echo "  • Test the popup now:   bash kiosk/morning-kiosk.sh   (Cmd+Q to quit)"
echo "  • Rehearse wake-sleep:  bash kiosk/rehearse.sh  then  pmset sleepnow"
echo "  • Log:  cat \"$LOG\""
echo "  • Undo: bash kiosk/uninstall.sh"
echo "  • Needs Google Chrome installed."
