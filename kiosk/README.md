# Morning Desk — laptop kiosk (personal Mac)

The kiosk pops up fullscreen only at **06:30** and **22:00**; the rest of the day
it's your normal desktop. **Cmd+Q** dismisses it.

How it works: a tiny background watcher (a bash loop, invisible, ~0 CPU) runs always
and opens the kiosk when the clock hits a scheduled time. `pmset` wakes the Mac at
those times; on wake the watcher resumes and fires. This avoids the flaky
"launchd launches an app on wake" path that failed earlier.

## Files
- `setup.sh` — one-time: no wake-password, mint token, write the launcher + watcher,
  schedule wakes, install the watcher agent (KeepAlive).
- `morning-kiosk.sh` / `kiosk-daemon.sh` — auto-generated (gitignored; token inside).
- `rehearse.sh` — one-off target ~2 min out to test wake-from-sleep now.
- `uninstall.sh` — remove everything.

## Install (on this laptop)
```bash
cd ~/Projects/morning-desk && git pull
bash kiosk/uninstall.sh        # clear any earlier agent
rm -f kiosk/morning-kiosk.sh   # regenerate the launcher
bash kiosk/setup.sh            # enter PIN + Mac passwords
```
Needs **Google Chrome**.

## Verify
- Watcher running:  `tail -3 ~/Library/Logs/morningdesk-kiosk.log` → "watcher started".
- Popup now:        `bash kiosk/morning-kiosk.sh`  (Cmd+Q to quit).
- Wake-from-sleep:  `bash kiosk/rehearse.sh`  then  `pmset sleepnow`.
- Watch live:       `tail -f ~/Library/Logs/morningdesk-kiosk.log`

## Undo / change times
- `bash kiosk/uninstall.sh`.
- Edit `MORNING` / `EVENING` in `setup.sh`, delete `morning-kiosk.sh`, re-run setup.
