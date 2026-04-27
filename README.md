# Fuji Refurb Watch

A Streamlit dashboard + Python checker that monitors Fujifilm refurbished camera stock, stores local run history in SQLite, and optionally sends Discord alerts for meaningful stock changes.

## What This Tool Does

- Fetches the Fujifilm refurbished camera listing page.
- Detects refurbished in-stock options by SKU (including variant info like color/style).
- Saves each run locally to SQLite (`data/fuji_watch.db`).
- Shows a dashboard with:
  - Current stock status by camera (in-stock first, sorted by SKU count)
  - Styled camera cards (images, specs, variant tags, feature badges)
  - Stock-change highlights since the previous run
  - Calendar of historical check dates
- Sends Discord alerts when configured (change-only or every run mode).

## Project Structure

- `scripts/checker.py`  
  Core scraping + comparison + persistence flow (`run_check`).
- `scripts/streamlit_app.py`  
  Streamlit UI, card rendering, history calendar, and user controls.
- `scripts/storage_sqlite.py`  
  SQLite schema/init + save/load history/state helpers.
- `data/fuji_watch.db`  
  Local runtime database (auto-created).
- `requirements.txt` / `pyproject.toml`  
  Dependencies.

## Requirements

- Python 3.10+ recommended
- `requests`, `bs4`, `streamlit`, `streamlit-calendar`

Install with your preferred method:

```bash
pip install -r requirements.txt
```

or:

```bash
uv sync
```

## Run the App

From project root:

```bash
PYTHONPATH="scripts" streamlit run scripts/streamlit_app.py
```

## Run a Direct Check (without UI)

```bash
PYTHONPATH="scripts" python -c "from checker import run_check; print(run_check(discord_notifications=False))"
```

## Discord Alerts

Set webhook in `.env`:

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

In the UI:
- `discord notifications`: enable/disable sending
- `only when change`: send only alert-worthy changes (`True`) or send every run summary (`False`)

## AI Placeholder (Claude or Similar)

A non-invasive placeholder hook is available in `scripts/checker.py`:
- Function: `build_ai_placeholder(changes_by_camera)`
- Result payload included in `run_check(...)` output as `ai_summary`
- Current behavior: no API call is made yet (`enabled: False`)

Optional environment variables for future wiring:

```env
AI_PROVIDER=claude
AI_MODEL=claude-3-5-sonnet
CLAUDE_API_KEY=...
# or
ANTHROPIC_API_KEY=...
```

When you are ready to integrate, replace the placeholder body with a real SDK/API call and set `summary` from model output.

## Camera Specs Source

Specs shown in cards are currently based on a curated hardcoded dictionary in `scripts/checker.py` (`CAMERA_SPECS`) for consistency and speed.

Displayed card specs:
- Image Sensor
- Processor
- LCD Monitor

Feature badges (Yes/No style):
- EVF
- IBIS
- Weather Sealed

## Card UI Notes

- Variant pills (Color/Style) are built from currently in-stock options only.
- If a camera is out of stock, variant pills are hidden.
- Color indicator dots appear in the image area for recognized colors.
- Card iframe height is calculated dynamically from card count and grid assumptions, with ResizeObserver fallback adjustment.

## Data & Privacy

- All run history is stored locally in SQLite (`data/fuji_watch.db`).
- No cloud database is required.
- Only outbound requests are to Fujifilm pages and optional Discord webhook.

## Troubleshooting

- If imports appear unresolved in editor but app runs fine, it may be the local interpreter selection.
- If Streamlit layout looks stale after CSS/HTML tweaks, hard refresh browser or restart Streamlit.
- If Discord alerts do not send, verify `DISCORD_WEBHOOK_URL` and UI toggles.

## Roadmap Ideas

- Move card renderer into a dedicated `camera_cards.py` module.
- Add configurable card density presets (2/3/4 columns).
- Add tests for parsing + change-detection logic.