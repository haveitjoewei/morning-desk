#!/bin/bash
# Remove the kiosk schedule.   bash kiosk/uninstall.sh
for L in com.morningdesk.kiosk com.morningdesk.rehearse; do
  P="$HOME/Library/LaunchAgents/$L.plist"
  launchctl unload "$P" 2>/dev/null || true
  rm -f "$P"
done
sudo pmset repeat cancel 2>/dev/null || true
sudo rm -f /etc/sudoers.d/morningdesk
echo "Kiosk schedule removed."
echo "(kiosk/morning-kiosk.sh kept — delete it to also remove the saved token.)"
