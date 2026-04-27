import json
import os
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from storage_sqlite import get_history, load_previous_state, save_state

BASE_DIR = Path(__file__).resolve().parent.parent
URL = "https://shopusa.fujifilm-x.com/refurbished/refurbished-cameras/"
DB_PATH = str(BASE_DIR / "data" / "fuji_watch.db")
DEFAULT_SELECTED_CAMERAS = ["X-M5", "X-H2", "X-T5", "X-S20"]
MAX_HISTORY_ENTRIES = 365

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def load_local_env():
    # Supports both project-local .env and parent .env.
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


def load_item_list_products(soup):
    products = {}
    for script_tag in soup.select('script[type="application/ld+json"]'):
        if not script_tag.string:
            continue
        try:
            data = json.loads(script_tag.string)
        except json.JSONDecodeError:
            continue
        blocks = data if isinstance(data, list) else [data]
        for block in blocks:
            if not isinstance(block, dict) or block.get("@type") != "ItemList":
                continue
            for entry in block.get("itemListElement", []):
                product = entry.get("item", {})
                name = product.get("name")
                offers = product.get("offers", [])
                if name and isinstance(offers, list):
                    products[name] = offers
    return products


def is_refurbished_in_stock(offer):
    condition = offer.get("itemCondition", "")
    availability = offer.get("availability", "")
    return condition.endswith("RefurbishedCondition") and availability.endswith("InStock")


def load_variant_details_by_sku(html_text):
    variant_by_sku = {}
    pattern = re.compile(
        r"initConfigurableOptions\(\s*'\d+'\s*,\s*(?P<payload>\{.*?\})\s*,\s*(?:true|false)\s*\)",
        re.DOTALL,
    )
    for match in pattern.finditer(html_text):
        try:
            payload = json.loads(match.group("payload"))
        except json.JSONDecodeError:
            continue
        attributes = payload.get("attributes", {})
        index = payload.get("index", {})
        sku_map = payload.get("sku", {})
        name_map = payload.get("name", {})

        attr_id_to_code = {}
        attr_option_labels = {}
        for attr_id, attr_data in attributes.items():
            attr_id_to_code[attr_id] = attr_data.get("code", "")
            labels = {}
            for option in attr_data.get("options", []):
                oid = option.get("id")
                if oid is not None:
                    labels[str(oid)] = option.get("label", "")
            attr_option_labels[attr_id] = labels

        for simple_id, selected in index.items():
            sku = sku_map.get(simple_id)
            if not sku:
                continue
            details = {"name": name_map.get(simple_id, "")}
            for attr_id, option_id in selected.items():
                code = attr_id_to_code.get(attr_id, attr_id)
                label = attr_option_labels.get(attr_id, {}).get(str(option_id), "")
                if label:
                    details[code] = label
            variant_by_sku[sku] = details
    return variant_by_sku


def snapshot_for_camera(offers, variant_by_sku):
    rows = []
    for offer in offers:
        if not is_refurbished_in_stock(offer):
            continue
        sku = str(offer.get("sku", ""))
        vd = variant_by_sku.get(sku, {})
        rows.append(
            {
                "sku": sku,
                "price": offer.get("price"),
                "url": offer.get("url", ""),
                "color": vd.get("color", "Unknown"),
                "style": vd.get("style", "Unknown"),
            }
        )
    skus = sorted(r["sku"] for r in rows if r["sku"])
    return {"refurb_in_stock": len(skus) > 0, "skus": skus, "options": rows}


def describe_change(camera_name, prev_snap, curr_snap):
    if prev_snap is None:
        return [f"{camera_name}: (no prior snapshot — baseline for this camera)"]
    p_in = prev_snap.get("refurb_in_stock", False)
    c_in = curr_snap.get("refurb_in_stock", False)
    prev_skus = set(prev_snap.get("skus", []))
    curr_skus = set(curr_snap.get("skus", []))

    if not p_in and c_in:
        return [f"{camera_name}: BACK IN STOCK (refurbished)"]
    if p_in and not c_in:
        return [f"{camera_name}: NOW OUT OF STOCK (refurbished)"]
    if p_in and c_in:
        added, removed = curr_skus - prev_skus, prev_skus - curr_skus
        if not added and not removed:
            return [f"{camera_name}: same in-stock refurbished SKUs"]
        lines = []
        if added:
            lines.append(f"{camera_name}: new SKUs: {', '.join(sorted(added))}")
        if removed:
            lines.append(f"{camera_name}: dropped SKUs: {', '.join(sorted(removed))}")
        return lines
    return [f"{camera_name}: still no refurbished in stock"]


def build_alert_lines(changes_by_camera):
    alert_lines = []
    for lines in changes_by_camera.values():
        for text in [line.strip() for line in lines]:
            if (
                "BACK IN STOCK" in text
                or "NOW OUT OF STOCK" in text
                or "new SKUs" in text
                or "dropped SKUs" in text
            ):
                alert_lines.append(text)
    return alert_lines


def send_discord_alert_if_needed(
    changes_by_camera,
    checked_at,
    discord_notifications=True,
    only_when_change=True,
):
    if not discord_notifications:
        return False, "Discord notifications disabled."

    webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return False, "Discord webhook not configured."

    alert_lines = build_alert_lines(changes_by_camera)
    send_no_change = not only_when_change
    if not alert_lines and not send_no_change:
        return False, "No alert-worthy changes."
    if not alert_lines:
        alert_lines = ["No stock changes detected in this run."]

    content = "\n".join(
        [
            "Fuji Refurb Watch Update",
            f"Checked at (Local): {checked_at}",
            "",
            *[f"- {line}" for line in alert_lines[:20]],
        ]
    )
    try:
        response = requests.post(webhook_url, json={"content": content}, timeout=20)
        response.raise_for_status()
        return True, "Discord alert sent."
    except requests.RequestException as exc:
        return False, f"Discord alert failed: {exc}"


def fetch_catalog():
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    products_by_name = load_item_list_products(soup)
    variant_by_sku = load_variant_details_by_sku(response.text)
    return products_by_name, variant_by_sku


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

    current = {
        name: snapshot_for_camera(products_by_name.get(name, []), variant_by_sku)
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
