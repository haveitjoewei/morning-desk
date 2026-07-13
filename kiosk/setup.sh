#!/bin/bash
# One-time kiosk setup on a PERSONAL Mac. A tiny background watcher opens the kiosk
# fullscreen only at the scheduled times; the rest of the day it's your normal
# desktop. Cmd+Q dismisses it.   bash kiosk/setup.sh
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER="$HERE/morning-kiosk.sh"
WATCHER="$HERE/kiosk-daemon.sh"
BASE="https://morning-desk-ashen.vercel.app"
MORNING="0630"           # HHMM (24h)
EVENING="2200"           # HHMM (24h)  (10pm)
UID_NUM="$(id -u)"; USER_NAME="$(id -un)"
LA="$HOME/Library/LaunchAgents"
PLIST="$LA/com.morningdesk.kiosk.plist"
LOG="$HOME/Library/Logs/morningdesk-kiosk.log"
MH=${MORNING:0:2}; MM=${MORNING:2:2}; EH=${EVENING:0:2}; EM=${EVENING:2:2}
mkdir -p "$LA" "$HOME/Library/Logs" "$HOME/Library/Application Support/morningdesk"
echo "Morning Desk kiosk — pops up at ${MH}:${MM} and ${EH}:${EM}, otherwise your normal desktop."

# 0. Passwordless pmset (schedule re-arms itself) + no wake password (else the kiosk
#    hides behind the lock screen).
echo "Configuring (needs your Mac password once)…"
echo "$USER_NAME ALL=(root) NOPASSWD: /usr/bin/pmset" | sudo tee /etc/sudoers.d/morningdesk >/dev/null
sudo chmod 440 /etc/sudoers.d/morningdesk
echo "Turning off the wake password (enter your Mac LOGIN password):"
sysadminctl -screenLock off -password - 2>/dev/null || echo "  ! set Lock Screen → 'Require password' → Never manually."

# 1. Mint token + launcher (opens Chrome kiosk, re-arms next wake, then exits).
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
/usr/bin/caffeinate -u -t 3 >/dev/null 2>&1 &
H=\$(date +%H)
if [ "\$H" -lt 12 ]; then
  sudo /usr/bin/pmset schedule wakeorpoweron "\$(date -v${EH}H -v${EM}M -v0S '+%m/%d/%y %H:%M:%S')" >>"\$LOG" 2>&1 || true
else
  sudo /usr/bin/pmset schedule wakeorpoweron "\$(date -v+1d -v${MH}H -v${MM}M -v0S '+%m/%d/%y %H:%M:%S')" >>"\$LOG" 2>&1 || true
fi
# Refresh the brief (schedule + priorities) from local connectors, in the background.
REPO="\$(cd "\$(dirname "\$0")/.." && pwd)"
TOKEN="\${URL##*k=}"
[ -f "\$HOME/.config/morning-desk/environment" ] && . "\$HOME/.config/morning-desk/environment"
(cd "\$REPO" && ./venv/bin/python -m orchestrator.publish_brief "\$TOKEN") >>"\$LOG" 2>&1 &
# Close any lingering kiosk window, then open a NEW instance via 'open -na' so macOS
# activates it and switches to its window (a plain background launch opens --kiosk on
# a separate Space you never see). Matches only the kiosk Chrome (its own data-dir).
pkill -f "morningdesk-kiosk" 2>/dev/null; sleep 2
open -na "Google Chrome" --args --kiosk --app="\$URL" \\
  --user-data-dir="\$HOME/.morningdesk-kiosk" \\
  --start-fullscreen \\
  --no-first-run --no-default-browser-check --disable-translate \\
  --disable-features=TranslateUI --overscroll-history-navigation=0 \\
  --disable-session-crashed-bubble --disable-infobars >>"\$LOG" 2>&1
echo "\$(date '+%F %T') chrome launched (open -na)" >> "\$LOG"
LAUNCHEOF
  chmod +x "$LAUNCHER"
  echo "  ✓ launcher written."
fi

# 2. Watcher: a background loop that fires the launcher at each scheduled minute.
#    Survives sleep (it just pauses); on wake it resumes, sees the time, and fires.
cat > "$WATCHER" <<WATCHEOF
#!/bin/bash
LOG="$LOG"; STAMP="\$HOME/Library/Application Support/morningdesk"
LAUNCHER="$LAUNCHER"; MORNING="$MORNING"; EVENING="$EVENING"
mkdir -p "\$STAMP"
echo "\$(date '+%F %T') watcher started" >> "\$LOG"
mins() { echo \$((10#\${1:0:2}*60 + 10#\${1:2:2})); }
while true; do
  NOW=\$(mins "\$(date +%H%M)"); TODAY=\$(date +%Y%m%d)
  TARGETS="\$MORNING \$EVENING"
  [ -f "\$STAMP/rehearse" ] && TARGETS="\$TARGETS \$(cat "\$STAMP/rehearse" 2>/dev/null)"
  for T in \$TARGETS; do
    D=\$((NOW - \$(mins "\$T")))
    # Fire anytime within 2h of the target (once/day) — so a missed scheduled wake
    # still shows the kiosk the moment you open the laptop that morning/evening.
    if [ "\$D" -ge 0 ] && [ "\$D" -le 120 ] && [ ! -f "\$STAMP/\$TODAY-\$T" ]; then
      touch "\$STAMP/\$TODAY-\$T"; rm -f "\$STAMP/rehearse"
      echo "\$(date '+%F %T') watcher firing \$T" >> "\$LOG"
      /bin/bash "\$LAUNCHER"
    fi
  done
  sleep 20
done
WATCHEOF
chmod +x "$WATCHER"

# 3. Wakes: repeating morning + arm tonight's evening.
sudo pmset repeat wakeorpoweron MTWRFSU "${MH}:${MM}:00"
sudo pmset schedule wakeorpoweron "$(date -v${EH}H -v${EM}M -v0S '+%m/%d/%y %H:%M:%S')" 2>/dev/null || true

# 4. Keep the (tiny, invisible) watcher running always.
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.morningdesk.kiosk</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$WATCHER</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict></plist>
PLISTEOF
launchctl bootout "gui/$UID_NUM" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$UID_NUM" "$PLIST"

echo
echo "Done. A background watcher is now running; the kiosk pops up at ${MH}:${MM} and ${EH}:${EM}."
echo "  • Confirm the watcher started:  tail -3 \"$LOG\"   (look for 'watcher started')"
echo "  • Test the popup now:           bash kiosk/morning-kiosk.sh   (Cmd+Q to quit)"
echo "  • Rehearse wake-sleep:          bash kiosk/rehearse.sh  then  pmset sleepnow"
echo "  • Undo:                         bash kiosk/uninstall.sh"
echo "  • Needs Google Chrome installed."
