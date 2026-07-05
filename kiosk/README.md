# Morning Desk — laptop kiosk

Turn a spare Mac into the morning/evening display. A fullscreen Chrome kiosk stays
**always open** (relaunched if it quits); the Mac wakes itself at **06:30** and
**22:00** so the display comes on showing it. No tablet, no PIN.

Why always-open: relying on a scheduled task to *launch* a browser on wake is
flaky. Instead the kiosk is already running, so a wake just needs to turn the
display on — which a scheduled `wakeorpoweron` does.

## Files
- `setup.sh` — one-time: disables the wake password, mints a no-PIN token, writes
  the launcher, schedules both wakes, and installs two launch agents (the kiosk +
  a background "rearm" that wakes the display and arms the next wake).
- `morning-kiosk.sh` / `rearm.sh` — auto-generated (gitignored; token inside).
- `rehearse.sh` — schedule a wake ~2 min out to test wake-from-sleep now.
- `uninstall.sh` — remove everything.

## Install (on the kiosk laptop)
```bash
cd ~/Projects/morning-desk && git pull
bash kiosk/setup.sh    # enter: dashboard PIN, Mac login password, Mac admin password
```
Needs **Google Chrome**. The kiosk opens immediately and stays open.

## Test
- **Now:** it should already be fullscreen. Quit for testing:
  `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.morningdesk.kiosk.plist`
- **Wake-from-sleep:** `bash kiosk/rehearse.sh`, then `pmset sleepnow`.
- **Diagnose:** `cat ~/Library/Logs/morningdesk-kiosk.log`

## Change times / undo
- Edit `MORNING` / `EVENING` in `setup.sh`, delete `morning-kiosk.sh`, re-run setup.
- `bash kiosk/uninstall.sh` removes the schedule (re-enable the wake password with
  `sysadminctl -screenLock immediate -password -`).
