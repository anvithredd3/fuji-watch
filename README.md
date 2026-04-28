# Fuji Refurb Watch

Fuji Refurb Watch is a Streamlit dashboard plus a Python checker that monitors Fujifilm refurbished camera stock, stores local run history in SQLite, and can send Discord alerts.

## What It Does

- Fetches Fujifilm refurbished camera listing data.
- Detects in-stock refurbished options by SKU and variant.
- Tracks changes versus previous run.
- Stores run history in `data/fuji_watch.db`.
- Provides a dashboard with stock tables, camera cards, change feed, history calendar, and AI Q&A.
- Supports AI responses via Claude or ChatGPT API.

## Project Structure (Package-Native)

- `scripts/checker.py`  
  Orchestrator and shared entrypoint used by UI and CLI.

- `scripts/backend/`  
  Backend/data logic:
  - `catalog.py` (fetch/parse catalog, variants, images)
  - `camera_specs.py` (hardcoded camera specs)
  - `alerts.py` (change detection + Discord alert dispatch)
  - `ai_service.py` (Claude/OpenAI provider routing + prompting)
  - `storage_sqlite.py` (SQLite persistence)

- `scripts/ui/`  
  UI logic:
  - `streamlit_app.py` (main Streamlit app)
  - `ui_camera_cards.py` (camera card renderer)

## Requirements

- Python 3.13+ (matches `pyproject.toml`)
- Dependencies from `requirements.txt`

Install:

```bash
pip install -r requirements.txt
```

or:

```bash
uv sync
```

## Run Commands

From project root:

```bash
PYTHONPATH="." streamlit run scripts/ui/streamlit_app.py
```

Direct checker run:

```bash
PYTHONPATH="." python scripts/checker.py
```

If using local virtualenv explicitly:

```bash
PYTHONPATH="." .venv/bin/streamlit run scripts/ui/streamlit_app.py
PYTHONPATH="." .venv/bin/python scripts/checker.py
```

## Environment Variables

Create/update `.env` as needed:

```env
# Discord (optional)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# AI defaults (optional)
AI_PROVIDER=claude      # claude | chatgpt
AI_MODEL=claude-3-5-sonnet-latest

# Claude
CLAUDE_API_KEY=...
# or
ANTHROPIC_API_KEY=...

# OpenAI / ChatGPT API
OPENAI_API_KEY=...
```

## AI Assistant Notes

- Sidebar lets you choose provider/model.
- Chat panel supports compact/expanded mode and scrollable history.
- AI answers are grounded in the latest run context (stock + specs loaded in app).

## Data and Privacy

- All history is local in `data/fuji_watch.db`.
- Outbound network calls are to:
  - Fujifilm catalog/product pages
  - Optional Discord webhook
  - Optional AI provider APIs (Claude/OpenAI)

## Troubleshooting

- `ModuleNotFoundError` for Streamlit-related packages:
  - reinstall dependencies with `pip install -r requirements.txt`
  - ensure interpreter points to project venv (`.venv/bin/python`)
- Imports failing after refactor:
  - run commands with `PYTHONPATH="."` from project root
- UI appears stale after styling updates:
  - restart Streamlit and hard refresh browser