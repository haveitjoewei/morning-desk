#!/bin/bash
# Remove the kiosk.   bash kiosk/uninstall.sh
UID_NUM="$(id -u)"
for L in com.morningdesk.kiosk com.morningdesk.rearm com.morningdesk.rehearse; do
  P="$HOME/Library/LaunchAgents/$L.plist"
  launchctl bootout "gui/$UID_NUM" "$P" 2>/dev/null || true
  launchctl unload "$P" 2>/dev/null || true
  rm -f "$P"
done
sudo pmset repeat cancel 2>/dev/null || true
sudo rm -f /etc/sudoers.d/morningdesk
pkill -f "morningdesk-kiosk" 2>/dev/null || true
echo "Kiosk removed. (kiosk/morning-kiosk.sh kept — delete it to remove the token.)"
echo "Re-enable the wake password if you want:  sysadminctl -screenLock immediate -password -"
