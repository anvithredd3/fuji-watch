import os
from datetime import datetime
from pathlib import Path

from scripts.backend.ai_service import (
    DEFAULT_AI_MODELS,
    ask_ai_about_stock,
    build_ai_placeholder,
    resolve_ai_settings,
)
from scripts.backend.alerts import describe_change, send_discord_alert_if_needed
from scripts.backend.catalog import URL, fetch_catalog, snapshot_for_camera
from scripts.backend.storage_sqlite import get_history, load_previous_state, save_state

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = str(BASE_DIR / "data" / "fuji_watch.db")
DEFAULT_SELECTED_CAMERAS = ["X-M5", "X-H2", "X-T5", "X-S20"]
MAX_HISTORY_ENTRIES = 365


def load_local_env():
    env_paths = [BASE_DIR / ".env", BASE_DIR.parent / ".env"]
    for env_path in env_paths:
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            os.environ.setdefault(key, value)


def get_available_cameras():
    products_by_name, _ = fetch_catalog()
    return sorted(products_by_name.keys())


def get_last_selected_cameras():
    previous = load_previous_state(DB_PATH)
    if not previous:
        return []
    return previous.get("selected_cameras", [])


def run_check(
    cameras=None,
    discord_notifications=True,
    only_when_change=True,
):
    load_local_env()
    products_by_name, variant_by_sku = fetch_catalog()
    available_cameras = sorted(products_by_name.keys())
    if cameras:
        selected_cameras = [name for name in cameras if name in products_by_name]
    else:
        selected_cameras = [n for n in DEFAULT_SELECTED_CAMERAS if n in products_by_name]
        if not selected_cameras:
            selected_cameras = available_cameras

    checked_at = datetime.now().astimezone().isoformat()
    previous = load_previous_state(DB_PATH)
    image_cache = {}

    current = {
        name: snapshot_for_camera(
            name,
            products_by_name.get(name, []),
            variant_by_sku,
            image_cache,
        )
        for name in selected_cameras
    }
    prev_cameras = (previous or {}).get("cameras", {})
    changes_by_camera = {}
    if previous is None or not prev_cameras:
        for name in selected_cameras:
            changes_by_camera[name] = [f"{name}: (No prior state file — baseline run.)"]
    else:
        for name in selected_cameras:
            changes_by_camera[name] = describe_change(name, prev_cameras.get(name), current[name])

    save_state(
        DB_PATH,
        checked_at=checked_at,
        source_url=URL,
        selected_cameras=selected_cameras,
        cameras=current,
    )
    history = get_history(DB_PATH, limit=MAX_HISTORY_ENTRIES)
    discord_sent, discord_message = send_discord_alert_if_needed(
        changes_by_camera=changes_by_camera,
        checked_at=checked_at,
        discord_notifications=discord_notifications,
        only_when_change=only_when_change,
    )
    ai_summary = build_ai_placeholder(changes_by_camera)

    return {
        "checked_at": checked_at,
        "previous_checked_at": previous.get("checked_at") if previous else None,
        "selected_cameras": selected_cameras,
        "available_cameras": available_cameras,
        "current": current,
        "changes_by_camera": changes_by_camera,
        "history": history,
        "discord_sent": discord_sent,
        "discord_message": discord_message,
        "discord_mode": {
            "notifications": discord_notifications,
            "only_when_change": only_when_change,
        },
        "ai_summary": ai_summary,
    }


def main():
    result = run_check()
    print(f"\nCheck time (Local): {result['checked_at']}")
    if result["previous_checked_at"]:
        print(f"Previous check (Local): {result['previous_checked_at']}")
    else:
        print("Previous check: (none)")
    print("\n--- Changes since last run ---")
    for name in result["selected_cameras"]:
        for line in result["changes_by_camera"][name]:
            print(f"  {line}")
    print(f"\nDiscord: {result['discord_message']}")
    print(f"Saved state to {DB_PATH}")


if __name__ == "__main__":
    main()
