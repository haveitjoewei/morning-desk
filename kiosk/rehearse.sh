#!/bin/bash
# Rehearse the real watcher from sleep: set a one-off target ~2 min out + wake the
# Mac then, so the background watcher fires the kiosk exactly like a real morning.
#   bash kiosk/rehearse.sh   then   pmset sleepnow
set -e
STAMP="$HOME/Library/Application Support/morningdesk"
mkdir -p "$STAMP"

T=$(date -v+2M +%H%M); WHEN=$(date -v+2M '+%m/%d/%y %H:%M:00'); HHMM=$(date -v+2M '+%H:%M')
echo "$T" > "$STAMP/rehearse"          # the watcher will fire at this minute
sudo /usr/bin/pmset schedule wakeorpoweron "$WHEN"

echo "One-off target set for $HHMM and a wake scheduled."
echo
echo "Now run:   pmset sleepnow"
echo "At $HHMM the Mac wakes and the watcher pops up the kiosk. Cmd+Q to quit."
echo "Watch it:  tail -f ~/Library/Logs/morningdesk-kiosk.log"
