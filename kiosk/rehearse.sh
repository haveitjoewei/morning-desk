#!/bin/bash
# Rehearse the scheduled kiosk from sleep: schedules a wake + a one-off launch ~2 min
# out, so you can sleep the Mac and watch it wake and pop up the kiosk.
#   bash kiosk/rehearse.sh   then   pmset sleepnow
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER="$HERE/morning-kiosk.sh"
UID_NUM="$(id -u)"
[ -f "$LAUNCHER" ] || { echo "Run kiosk/setup.sh first."; exit 1; }

WHEN=$(date -v+2M '+%m/%d/%y %H:%M:00')
HH=$(date -v+2M +%H); MM=$(date -v+2M +%M); HHMM=$(date -v+2M '+%H:%M')
TMP="$HOME/Library/LaunchAgents/com.morningdesk.rehearse.plist"

echo "Scheduling a wake at $HHMM…"
sudo /usr/bin/pmset schedule wakeorpoweron "$WHEN"

cat > "$TMP" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.morningdesk.rehearse</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$LAUNCHER</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>$((10#$HH))</integer><key>Minute</key><integer>$((10#$MM))</integer></dict>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/morningdesk-kiosk.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/morningdesk-kiosk.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$UID_NUM" "$TMP" 2>/dev/null || true
launchctl bootstrap "gui/$UID_NUM" "$TMP"

echo
echo "Now run:   pmset sleepnow"
echo "At $HHMM the Mac wakes and the kiosk pops up. Cmd+Q to quit."
echo "Clean up:  launchctl bootout gui/$UID_NUM \"$TMP\" && rm \"$TMP\""
echo "Log:       cat ~/Library/Logs/morningdesk-kiosk.log"
