# Morning Desk — go-live setup

Run everything from the project root with the venv python:

```bash
cd ~/Projects/morning-desk
```

Check progress at any time:

```bash
./venv/bin/python -m scripts.status
```

You're fully live when `claude`, `google_calendar`, and `gmail` all show `true`.

---

## 1. Claude API key (powers briefing, journal, outfit, urgency)

1. Go to <https://console.anthropic.com> → **Settings → API Keys → Create Key**. Copy it
   (starts with `sk-ant-`).
2. Open the env file (already created for you, perms 600):

   ```bash
   open -e ~/.config/morning-desk/environment
   ```

3. Put the key on the `ANTHROPIC_API_KEY=` line, e.g.:

   ```
   ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
   ```

   Save. Confirm: `./venv/bin/python -m scripts.status` → `claude.configured: true`.

---

## 2. Google Cloud project (one project serves both Calendar and Gmail)

1. Go to <https://console.cloud.google.com>. Top bar → project dropdown → **New Project**,
   name it `morning-desk`, Create, then select it.
2. **Enable the two APIs.** For each, search it in the top search bar, open it, click
   **Enable**:
   - "Google Calendar API"
   - "Gmail API"
3. **OAuth consent screen** (left menu → APIs & Services → OAuth consent screen):
   - User type: **External** → Create.
   - App name `morning-desk`, your email for support + developer contact → Save and
     continue through the screens.
   - On **Test users**, click **Add Users**, add your own Gmail address. Save.
     (Keeping the app in "Testing" is fine — it just means only your test users can log in.)
4. **Create the credential** (APIs & Services → Credentials → **Create Credentials** →
   **OAuth client ID**):
   - Application type: **Desktop app**, name `morning-desk-desktop` → Create.
   - Click **Download JSON** on the dialog.

---

## 3. Place the credential file (same file works for both)

Move the downloaded file into place under both names:

```bash
# adjust the source path to wherever your browser saved it
cp ~/Downloads/client_secret_*.json ~/.config/morning-desk/gcal_credentials.json
cp ~/.config/morning-desk/gcal_credentials.json ~/.config/morning-desk/gmail_credentials.json
chmod 600 ~/.config/morning-desk/gcal_credentials.json ~/.config/morning-desk/gmail_credentials.json
```

---

## 4. Authorize (one-time browser consent each)

Run each command, a browser opens, log in with the test-user account, click through the
"Google hasn't verified this app" → **Continue**, then **Allow**. A token file is written.

```bash
./venv/bin/python -m connectors.calendar_google --auth   # Calendar
./venv/bin/python -m connectors.airbnb_gmail --auth       # Gmail (Airbnb + VA share this)
```

Confirm: `./venv/bin/python -m scripts.status` → `google_calendar.token` and
`gmail.token` both `true`.

---

## 5. VA inbox label (optional, for the VA priority feed)

The VA connector reads Gmail messages labelled **VA** by default.

- In Gmail, create a label `VA`, then a filter that applies it to whatever your VA forwards
  (e.g. matches their email address). Newer-than-2-days mail with that label surfaces.
- Or point it at a different query without touching Gmail labels by setting
  `MD_VA_QUERY` in `~/.config/morning-desk/environment`, e.g.
  `MD_VA_QUERY=from:assistant@example.com newer_than:2d`.

Same idea for Airbnb via `MD_AIRBNB_QUERY` (default `from:airbnb.com newer_than:2d`).

---

## 6. Location (weather)

`config/location.json` is set to Sydney. Change `latitude`/`longitude`/`timezone`/`label`
if you're elsewhere. Coordinates: search your city on <https://www.latlong.net>.

---

## 7. Generate the real briefing

```bash
./venv/bin/python -m scripts.morning
```

Prints the weather line and writes `renderer/latest.png`. Open it:

```bash
open renderer/latest.png
```

If any source isn't configured yet, that block falls back to placeholder data — the rest
still renders.
