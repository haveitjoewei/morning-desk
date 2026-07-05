#!/bin/bash
# Dress rehearsal: wake the Mac in ~2 min and open the kiosk, so you can sleep it and
# watch exactly what tomorrow morning will look like.   bash kiosk/rehearse.sh
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER="$HERE/morning-kiosk.sh"
[ -f "$LAUNCHER" ] || { echo "Run kiosk/setup.sh first."; exit 1; }

WHEN=$(date -v+2M '+%m/%d/%y %H:%M:00')
HH=$(date -v+2M +%H); MM=$(date -v+2M +%M)
HHMM=$(date -v+2M '+%H:%M')
TMP="$HOME/Library/LaunchAgents/com.morningdesk.rehearse.plist"

echo "Scheduling a one-off wake at $HHMM …"
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
  <key>RunAtLoad</key><false/>
</dict></plist>
EOF
launchctl unload "$TMP" 2>/dev/null || true
launchctl load "$TMP"

echo
echo "Now run:   pmset sleepnow"
echo "The Mac wakes at $HHMM and opens the kiosk. Cmd+Q to quit."
echo "If it doesn't appear, check the log:  cat ~/Library/Logs/morningdesk-kiosk.log"
echo "Then clean up:  launchctl unload \"$TMP\" && rm \"$TMP\""
