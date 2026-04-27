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

CAMERA_SPECS = {
    "X-T5": [
        ("Image Sensor", "40.2MP X-Trans CMOS 5 HR BSI"),
        ("Image Processing Engine", "X-Processor 5"),
        ("EVF", "Yes - 3.69M-dot OLED, 0.8x"),
        ("LCD Monitor", "3.0-inch 3-way tilt touchscreen"),
        ("IBIS", "Yes - 5-axis, up to 7.0 stops"),
        ("Weather Sealed", "Yes - 56 points"),
    ],
    "X-H2": [
        ("Image Sensor", "40.2MP X-Trans CMOS 5 HR BSI"),
        ("Image Processing Engine", "X-Processor 5"),
        ("EVF", "Yes - 5.76M-dot OLED, 0.8x"),
        ("LCD Monitor", "3.0-inch vari-angle touchscreen"),
        ("IBIS", "Yes - 5-axis, up to 7.0 stops"),
        ("Weather Sealed", "Yes"),
    ],
    "X-E5": [
        ("Image Sensor", "40.2MP X-Trans CMOS 5 HR BSI"),
        ("Image Processing Engine", "X-Processor 5"),
        ("EVF", "Yes - 2.36M-dot OLED, 0.62x"),
        ("LCD Monitor", "3.0-inch tilt touchscreen"),
        ("IBIS", "Yes - 5-axis, up to 7.0 stops"),
        ("Weather Sealed", "No"),
    ],
    "X-S20": [
        ("Image Sensor", "26.1MP X-Trans CMOS 4 BSI"),
        ("Image Processing Engine", "X-Processor 5"),
        ("EVF", "Yes - 2.36M-dot OLED, 0.62x"),
        ("LCD Monitor", "3.0-inch vari-angle touchscreen"),
        ("IBIS", "Yes - 5-axis, up to 7.0 stops"),
        ("Weather Sealed", "Yes"),
    ],
    "X-T50": [
        ("Image Sensor", "40.2MP X-Trans CMOS 5 HR BSI"),
        ("Image Processing Engine", "X-Processor 5"),
        ("EVF", "Yes - 2.36M-dot OLED, 0.62x"),
        ("LCD Monitor", "3.0-inch vari-angle touchscreen"),
        ("IBIS", "Yes - 5-axis, up to 7.0 stops"),
        ("Weather Sealed", "No"),
    ],
    "X-T30 III": [
        ("Image Sensor", "26.1MP X-Trans CMOS 4 BSI"),
        ("Image Processing Engine", "X-Processor 5"),
        ("EVF", "Yes - 2.36M-dot OLED, 0.62x"),
        ("LCD Monitor", "3.0-inch tilt touchscreen"),
        ("IBIS", "No"),
        ("Weather Sealed", "No"),
    ],
    "X-M5": [
        ("Image Sensor", "26.1MP X-Trans CMOS 4 BSI"),
        ("Image Processing Engine", "X-Processor 5"),
        ("EVF", "No"),
        ("LCD Monitor", "3.0-inch vari-angle touchscreen"),
        ("IBIS", "No"),
        ("Weather Sealed", "No"),
    ],
    "X-M5 CN": [
        ("Image Sensor", "26.1MP X-Trans CMOS 4 BSI"),
        ("Image Processing Engine", "X-Processor 5"),
        ("EVF", "No"),
        ("LCD Monitor", "3.0-inch vari-angle touchscreen"),
        ("IBIS", "No"),
        ("Weather Sealed", "No"),
    ],
    "X-T200": [
        ("Image Sensor", "24.2MP APS-C Bayer CMOS BSI"),
        ("Image Processing Engine", "X-Processor 4"),
        ("EVF", "Yes - 2.36M-dot OLED, 0.62x"),
        ("LCD Monitor", "3.5-inch vari-angle touchscreen"),
        ("IBIS", "No"),
        ("Weather Sealed", "No"),
    ],
    "X half": [
        ("Image Sensor", "18MP 1-inch BSI CMOS (vertical mount)"),
        ("Image Processing Engine", "X-Processor 5"),
        ("EVF", "Optical only - 0.38x, no overlays"),
        ("LCD Monitor", "Rear LCD + sub front screen"),
        ("IBIS", "No"),
        ("Weather Sealed", "No"),
    ],
    "GFX-50R": [
        ("Image Sensor", "51.4MP Medium Format CMOS (43.8x32.9mm)"),
        ("Image Processing Engine", "X-Processor Pro"),
        ("EVF", "Yes - 3.69M-dot OLED, 0.77x"),
        ("LCD Monitor", "3.2-inch 2-way tilt touchscreen"),
        ("IBIS", "No"),
        ("Weather Sealed", "Yes - dust & moisture resistant"),
    ],
    "GFX100RF": [
        ("Image Sensor", "102MP Medium Format BSI CMOS II (43.8x32.9mm)"),
        ("Image Processing Engine", "X-Processor 5"),
        ("EVF", "Yes - 5.76M-dot OLED, 0.84x"),
        ("LCD Monitor", "3.2-inch 3-way tilt touchscreen"),
        ("IBIS", "No"),
        ("Weather Sealed", "Partial - adapter + filter required"),
    ],
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


def _extract_specs_from_soup(soup, max_specs=5):
    specs = []
    seen_keys = set()

    # Most specific: specs area by known id/anchors.
    for li in soup.select("#product-attributes li, [id*='product-attributes'] li"):
        text = li.get_text(" ", strip=True).lstrip("•- ").strip()
        if not text:
            continue
        if ":" in text:
            key, value = [p.strip() for p in text.split(":", 1)]
        elif " - " in text:
            key, value = [p.strip() for p in text.split(" - ", 1)]
        else:
            # Fallback when bullet is sentence-like.
            key = f"Spec {len(specs) + 1}"
            value = text
        if key and value and key not in seen_keys:
            specs.append({"key": key, "value": value})
            seen_keys.add(key)
        if len(specs) >= max_specs:
            return specs

    # Generic fallback: definition lists.
    for dl in soup.select("dl"):
        for dt, dd in zip(dl.select("dt"), dl.select("dd")):
            key = dt.get_text(" ", strip=True)
            value = dd.get_text(" ", strip=True)
            if key and value and key not in seen_keys:
                specs.append({"key": key, "value": value})
                seen_keys.add(key)
            if len(specs) >= max_specs:
                return specs

    # Fallback for Fujifilm product pages: derive compact specs from bullet text.
    bullet_texts = [
        li.get_text(" ", strip=True).lstrip("•- ").strip()
        for li in soup.select(".product-info-main li")
        if li.get_text(" ", strip=True).strip()
    ]
    derived = []
    for text in bullet_texts:
        lower = text.lower()
        if "sensor" in lower and not any(s["key"] == "Sensor" for s in derived):
            derived.append({"key": "Sensor", "value": text})
        elif (
            ("in-body image stabilization" in lower or "ibis" in lower or "stops" in lower)
            and not any(s["key"] == "Stabilisation" for s in derived)
        ):
            derived.append({"key": "Stabilisation", "value": text})
        elif (
            ("6.2k" in lower or "8k" in lower or "4k" in lower or "video" in lower)
            and not any(s["key"] == "Video" for s in derived)
        ):
            derived.append({"key": "Video", "value": text})
        elif ("shutter" in lower and not any(s["key"] == "Shutter" for s in derived)):
            derived.append({"key": "Shutter", "value": text})
        elif ("evf" in lower and not any(s["key"] == "EVF" for s in derived)):
            derived.append({"key": "EVF", "value": text})
        if len(derived) >= max_specs:
            break

    if derived:
        return derived[:max_specs]

    return specs


def _hardcoded_specs(camera_name, max_specs=5):
    entries = CAMERA_SPECS.get(camera_name, [])
    specs = [{"key": key, "value": value} for key, value in entries if key and value]
    return specs[:max_specs]


def fetch_product_page_details(product_url):
    if not product_url:
        return {"product_url": "", "image_url": "", "specs": []}
    try:
        response = requests.get(product_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException:
        return {"product_url": product_url, "image_url": "", "specs": []}

    soup = BeautifulSoup(response.text, "html.parser")
    image_url = ""
    og_image = soup.select_one('meta[property="og:image"]')
    if og_image and og_image.get("content"):
        image_url = og_image.get("content", "").strip()
    if not image_url:
        img = soup.select_one("img.product-image-photo, img.fotorama__img, img")
        if img and img.get("src"):
            image_url = img.get("src", "").strip()

    return {
        "product_url": product_url,
        "image_url": image_url,
        "specs": _extract_specs_from_soup(soup, max_specs=5),
    }


def fetch_image_for_url(url, image_cache):
    if not url:
        return ""
    cached = image_cache.get(url)
    if cached is not None:
        return cached
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
    except requests.RequestException:
        image_cache[url] = ""
        return ""

    soup = BeautifulSoup(response.text, "html.parser")
    image_url = ""
    og_image = soup.select_one('meta[property="og:image"]')
    if og_image and og_image.get("content"):
        image_url = og_image.get("content", "").strip()
    if not image_url:
        img = soup.select_one("img.product-image-photo, img.fotorama__img, img")
        if img and img.get("src"):
            image_url = img.get("src", "").strip()
    image_cache[url] = image_url
    return image_url


def snapshot_for_camera(camera_name, offers, variant_by_sku, page_details_cache):
    product_url = next((o.get("url", "") for o in offers if o.get("url")), "")
    page_details = page_details_cache.get(product_url)
    if page_details is None:
        page_details = fetch_product_page_details(product_url)
        page_details_cache[product_url] = page_details

    image_cache = page_details_cache.setdefault("_offer_image_cache", {})
    rows = []
    all_rows = []
    for offer in offers:
        sku = str(offer.get("sku", ""))
        vd = variant_by_sku.get(sku, {})
        offer_url = offer.get("url", "")
        raw_style = vd.get("style", "Unknown")
        normalized_style = raw_style.strip() if isinstance(raw_style, str) else "Unknown"
        if not normalized_style or normalized_style.lower() == "unknown":
            normalized_style = "Body Only"
        row = {
            "sku": sku,
            "price": offer.get("price"),
            "url": offer_url,
            "color": vd.get("color", "Unknown"),
            "style": normalized_style,
            "image_url": fetch_image_for_url(offer_url, image_cache),
            "in_stock": bool(is_refurbished_in_stock(offer)),
        }
        all_rows.append(row)
        if row["in_stock"]:
            rows.append(row)
    skus = sorted(r["sku"] for r in rows if r["sku"])
    available_colors = sorted(
        {r["color"] for r in all_rows if r.get("color") and r.get("color") != "Unknown"}
    )
    available_styles = sorted(
        {r["style"] for r in all_rows if r.get("style") and r.get("style") != "Unknown"}
    )
    specs = _hardcoded_specs(camera_name, max_specs=5)
    if not specs:
        specs = page_details.get("specs", [])
    return {
        "refurb_in_stock": len(skus) > 0,
        "skus": skus,
        "options": rows,
        "all_options": all_rows,
        "available_colors": available_colors,
        "available_styles": available_styles,
        "product_url": page_details.get("product_url", ""),
        "image_url": page_details.get("image_url", ""),
        "specs": specs,
    }


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


def build_ai_placeholder(changes_by_camera):
    """Placeholder hook for future Claude/LLM integration."""
    provider = os.getenv("AI_PROVIDER", "claude").strip().lower() or "claude"
    model = os.getenv("AI_MODEL", "claude-3-5-sonnet").strip() or "claude-3-5-sonnet"
    api_key_configured = bool(
        os.getenv("CLAUDE_API_KEY", "").strip() or os.getenv("ANTHROPIC_API_KEY", "").strip()
    )
    candidate_lines = build_alert_lines(changes_by_camera)
    return {
        "enabled": False,
        "provider": provider,
        "model": model,
        "api_key_configured": api_key_configured,
        "summary": "",
        "message": (
            "AI summary placeholder only. "
            "Wire your provider SDK/API call here when ready."
        ),
        "candidate_change_count": len(candidate_lines),
    }


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
    page_details_cache = {}

    current = {
        name: snapshot_for_camera(
            name,
            products_by_name.get(name, []),
            variant_by_sku,
            page_details_cache,
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
