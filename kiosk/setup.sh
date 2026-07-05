#!/bin/bash
# One-time kiosk setup for the Morning Desk dashboard on macOS.
# Run this ON THE LAPTOP you want as the morning display:  bash kiosk/setup.sh
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER="$HERE/morning-kiosk.sh"
WAKE_HHMM="06:30:00"     # when the Mac wakes
RUN_HOUR=6               # when the dashboard opens (a minute after wake)
RUN_MIN=31
LABEL="com.morningdesk.kiosk"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ ! -x "$LAUNCHER" ]; then echo "Missing $LAUNCHER"; exit 1; fi

echo "1/3  Scheduling the Mac to wake every day at ${WAKE_HHMM} (needs your password)…"
sudo pmset repeat wakeorpoweron MTWRFSU "$WAKE_HHMM"

echo "2/3  Installing the launch agent…"
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

echo "3/3  Done."
echo
echo "  • Mac wakes ${WAKE_HHMM}, dashboard opens ${RUN_HOUR}:${RUN_MIN} in fullscreen kiosk."
echo "  • Test it right now:      bash kiosk/morning-kiosk.sh"
echo "  • Exit kiosk Chrome:      Cmd+Q  (or Ctrl+Cmd+Q to lock)"
echo "  • Stop the schedule:      launchctl unload \"$PLIST\"  &&  sudo pmset repeat cancel"
echo "  • Change the time:        edit WAKE_HHMM / RUN_MIN in this script and re-run."
