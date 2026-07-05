#!/bin/bash
# One-time kiosk setup for the Morning Desk dashboard on macOS.
# Keeps a fullscreen Chrome kiosk ALWAYS open (relaunched if it quits) and wakes the
# Mac twice a day so the display comes on showing it. Run on the display laptop:
#   bash kiosk/setup.sh
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER="$HERE/morning-kiosk.sh"
REARM="$HERE/rearm.sh"
BASE="https://morning-desk-ashen.vercel.app"
MORNING="06:30"          # HH:MM (24h) wake #1
EVENING="22:00"          # HH:MM (24h) wake #2  (10pm)
UID_NUM="$(id -u)"
USER_NAME="$(id -un)"
LA="$HOME/Library/LaunchAgents"
KIOSK_PLIST="$LA/com.morningdesk.kiosk.plist"
REARM_PLIST="$LA/com.morningdesk.rearm.plist"
LOG="$HOME/Library/Logs/morningdesk-kiosk.log"

MH=${MORNING%:*}; MM=${MORNING#*:}
EH=${EVENING%:*}; EM=${EVENING#*:}
mkdir -p "$LA" "$HOME/Library/Logs"

echo "Morning Desk kiosk — always-on display, waking $MORNING and $EVENING."

# 0. Passwordless pmset (so the schedule can re-arm itself).
echo "Configuring (needs your Mac password once)…"
echo "$USER_NAME ALL=(root) NOPASSWD: /usr/bin/pmset" | sudo tee /etc/sudoers.d/morningdesk >/dev/null
sudo chmod 440 /etc/sudoers.d/morningdesk

# 0b. Don't ask for a password on wake, or the kiosk sits behind the lock screen.
echo "Turning off the wake password (enter your Mac LOGIN password):"
sysadminctl -screenLock off -password - 2>/dev/null || \
  echo "  ! do it manually: Lock Screen → 'Require password' → Never."
defaults -currentHost write com.apple.screensaver idleTime 0 2>/dev/null || true

# 1. Mint a long-lived no-PIN token + write the launcher (Chrome in foreground so
#    launchd's KeepAlive can relaunch it if it ever quits).
if [ ! -f "$LAUNCHER" ]; then
  printf "Your Morning Desk PIN (Joseph): "; read -rs PIN; echo
  RESP="$(curl -s -X POST "$BASE/api/unlock" -H 'Content-Type: application/json' -d "{\"pin\":\"$PIN\",\"kiosk\":true}")"
  TOKEN="$(printf '%s' "$RESP" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')"
  [ -z "$TOKEN" ] && { echo "Wrong PIN?"; exit 1; }
  cat > "$LAUNCHER" <<LAUNCHEOF
#!/bin/bash
# Morning Desk kiosk (auto-generated; contains a device token — keep private).
URL="$BASE/dashboard?k=$TOKEN"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
echo "\$(date '+%F %T') kiosk starting" >> "$LOG"
/usr/bin/caffeinate -u -t 3 >/dev/null 2>&1 &   # wake the display
exec "\$CHROME" --kiosk --app="\$URL" --user-data-dir="\$HOME/.morningdesk-kiosk" \\
  --no-first-run --no-default-browser-check --disable-translate \\
  --disable-features=TranslateUI --overscroll-history-navigation=0 \\
  --disable-session-crashed-bubble --disable-infobars
LAUNCHEOF
  chmod +x "$LAUNCHER"
  echo "  ✓ launcher written."
fi

# rearm helper: wakes the display + arms the next wake. Runs at both times.
cat > "$REARM" <<REARMEOF
#!/bin/bash
LOG="$LOG"
/usr/bin/caffeinate -u -t 5 >/dev/null 2>&1 &
H=\$(date +%H)
if [ "\$H" -lt 12 ]; then
  sudo /usr/bin/pmset schedule wakeorpoweron "\$(date -v${EH}H -v${EM}M -v0S '+%m/%d/%y %H:%M:%S')" >>"\$LOG" 2>&1 || true
fi
echo "\$(date '+%F %T') rearm ran (\$H)" >> "\$LOG"
REARMEOF
chmod +x "$REARM"

# 2. Wakes: repeating morning + arm tonight's evening now.
sudo pmset repeat wakeorpoweron MTWRFSU "${MORNING}:00"
sudo pmset schedule wakeorpoweron "$(date -v${EH}H -v${EM}M -v0S '+%m/%d/%y %H:%M:%S')" 2>/dev/null || true

# 3. Kiosk agent — always open (relaunch if it quits).
cat > "$KIOSK_PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.morningdesk.kiosk</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$LAUNCHER</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict></plist>
PLISTEOF

# 4. Rearm agent — fires at both wake times (background), wakes display + arms next.
cat > "$REARM_PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.morningdesk.rearm</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$REARM</string></array>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Hour</key><integer>$((10#$MH))</integer><key>Minute</key><integer>$((10#$MM + 1))</integer></dict>
    <dict><key>Hour</key><integer>$((10#$EH))</integer><key>Minute</key><integer>$((10#$EM + 1))</integer></dict>
  </array>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict></plist>
PLISTEOF

# 5. Load both with the modern API (launchctl load is unreliable on recent macOS).
for P in "$KIOSK_PLIST" "$REARM_PLIST"; do
  launchctl bootout "gui/$UID_NUM" "$P" 2>/dev/null || true
  launchctl bootstrap "gui/$UID_NUM" "$P"
done

echo
echo "Done. The kiosk should open now and stay open; the Mac wakes $MORNING and $EVENING."
echo "  • It's open? Good. Quit for testing: launchctl bootout gui/$UID_NUM \"$KIOSK_PLIST\""
echo "  • Rehearse a wake:  bash kiosk/rehearse.sh  then  pmset sleepnow"
echo "  • Log:  cat \"$LOG\""
echo "  • Undo:  bash kiosk/uninstall.sh"
echo "  • Needs Google Chrome installed."
