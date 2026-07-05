# Morning Desk — laptop kiosk

Turn a spare Mac into the morning display: it wakes itself, opens the dashboard
fullscreen (no PIN), and lets you tap the outfit to adjust — no tablet needed.

## What's here
- `morning-kiosk.sh` — launches Chrome in kiosk mode on the dashboard (token baked in,
  so it auto-signs-in as Joseph). Also `caffeinate`s the screen awake for 3 hours.
- `setup.sh` — one-time install: schedules the wake (`pmset`) + a launch agent
  (`launchd`) that runs the launcher a minute after wake.

## Install (on the kiosk laptop)
```bash
cd ~/Projects/morning-desk
bash kiosk/setup.sh        # asks for your password once (for the wake schedule)
```
Defaults: wake 06:30, dashboard opens 06:31, every day.

## Try it now
```bash
bash kiosk/morning-kiosk.sh   # opens the fullscreen kiosk immediately
```
Quit kiosk Chrome with **Cmd+Q**.

## Notes
- Install **Google Chrome** first (the launcher uses it for true `--kiosk`).
- Uses the laptop's own screen — no external monitor / flaky cable.
- The token in `morning-kiosk.sh` is a bearer credential for this device; keep the
  file private (it's gitignored).
- Evangeline's closet is one tap away on the dashboard (enter her PIN once).
- Change the time / weekends-only: edit `WAKE_HHMM` and the launch-agent minute in
  `setup.sh`, then re-run it.
- Undo everything: `launchctl unload ~/Library/LaunchAgents/com.morningdesk.kiosk.plist && sudo pmset repeat cancel`.
