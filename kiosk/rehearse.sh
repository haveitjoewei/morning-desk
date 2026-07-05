#!/bin/bash
# Rehearse a real wake-from-sleep. The kiosk stays open, so this just schedules a
# wake ~2 min out — sleep the Mac and the kiosk should be on screen when it wakes.
#   bash kiosk/rehearse.sh   then   pmset sleepnow
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
UID_NUM="$(id -u)"

echo "Making sure the kiosk is running…"
launchctl kickstart -k "gui/$UID_NUM/com.morningdesk.kiosk" 2>/dev/null || \
  { bash "$HERE/morning-kiosk.sh" >/dev/null 2>&1 & }
sleep 1

WHEN=$(date -v+2M '+%m/%d/%y %H:%M:00'); HHMM=$(date -v+2M '+%H:%M')
echo "Scheduling a wake at $HHMM…"
sudo /usr/bin/pmset schedule wakeorpoweron "$WHEN"

echo
echo "Now run:   pmset sleepnow"
echo "At $HHMM the Mac wakes and the kiosk should already be on screen."
echo "If the screen stays dark or shows the desktop, check:"
echo "   cat ~/Library/Logs/morningdesk-kiosk.log"
