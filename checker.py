import json
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

URL = "https://shopusa.fujifilm-x.com/refurbished/refurbished-cameras/"
STATE_PATH = "check_state.json"
TARGET_CAMERAS = ["X-E5", "X-M5", "X-S20", "X-H2", "X-T5"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


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
    return condition.endswith("RefurbishedCondition") and availability.endswith(
        "InStock"
    )


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


def load_previous_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_state(path, state):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


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
        return [
            f"  {camera_name}: (no prior snapshot — baseline for this camera)"
        ]
    p_in = prev_snap.get("refurb_in_stock", False)
    c_in = curr_snap.get("refurb_in_stock", False)
    prev_skus, curr_skus = set(prev_snap.get("skus", [])), set(curr_snap.get("skus", []))

    if not p_in and c_in:
        return [f"  {camera_name}: BACK IN STOCK (refurbished)"]
    if p_in and not c_in:
        return [f"  {camera_name}: NOW OUT OF STOCK (refurbished)"]
    if p_in and c_in:
        added, removed = curr_skus - prev_skus, prev_skus - curr_skus
        if not added and not removed:
            return [f"  {camera_name}: same in-stock refurbished SKUs"]
        lines = []
        if added:
            lines.append(f"  {camera_name}: new SKUs: {', '.join(sorted(added))}")
        if removed:
            lines.append(f"  {camera_name}: dropped SKUs: {', '.join(sorted(removed))}")
        return lines
    return [f"  {camera_name}: still no refurbished in stock"]


def main():
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    products_by_name = load_item_list_products(soup)
    variant_by_sku = load_variant_details_by_sku(response.text)

    checked_at = datetime.now(timezone.utc).isoformat()
    previous = load_previous_state(STATE_PATH)

    print(f"\nCheck time (UTC): {checked_at}")
    if previous and previous.get("checked_at"):
        print(f"Previous check (UTC): {previous['checked_at']}")
    else:
        print("Previous check: (none)")

    current = {
        name: snapshot_for_camera(products_by_name.get(name, []), variant_by_sku)
        for name in TARGET_CAMERAS
    }

    print("\n--- Today's status ---")
    for name in TARGET_CAMERAS:
        snap = current[name]
        print(f"\n{name}:")
        if not snap["refurb_in_stock"]:
            print("  Refurbished status: Out of Stock")
            continue
        print("  Refurbished status: In Stock")
        print("  In-stock refurbished options:")
        for opt in snap["options"]:
            print(
                f"    - SKU: {opt['sku']}, Color: {opt['color']}, Style: {opt['style']}, "
                f"Price: ${opt['price']}, URL: {opt['url']}"
            )

    print("\n--- Changes since last run ---")
    prev_cameras = (previous or {}).get("cameras", {})
    if previous is None or not prev_cameras:
        print("  (No prior state file — this run is the baseline.)")
    else:
        for name in TARGET_CAMERAS:
            for line in describe_change(name, prev_cameras.get(name), current[name]):
                print(line)

    save_state(
        STATE_PATH,
        {
            "version": 1,
            "checked_at": checked_at,
            "source_url": URL,
            "cameras": current,
        },
    )
    print(f"\nSaved state to {STATE_PATH}")


if __name__ == "__main__":
    main()
