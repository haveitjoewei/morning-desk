#!/bin/bash
# Stop the kiosk laptop from asking for a password on wake, so it comes straight to
# the desktop and the dashboard is visible. Run once on the kiosk Mac.
#   bash kiosk/nolock.sh
set -e

echo "Disabling the wake/lock password."
echo "Enter this Mac's LOGIN password when prompted:"
# Ventura+ : turn off "require password after sleep / screen saver".
if sysadminctl -screenLock off -password - ; then
  echo "  ✓ wake password off."
else
  echo "  ! sysadminctl failed (older macOS?). Do it manually:"
  echo "    System Settings → Lock Screen → 'Require password after…' → Never."
fi

# Don't let the screen saver kick in (it can re-arm a lock).
defaults -currentHost write com.apple.screensaver idleTime 0 2>/dev/null || true

echo
echo "Done — the Mac now wakes straight to the desktop."
echo "Re-enable later:  sysadminctl -screenLock immediate -password -"
