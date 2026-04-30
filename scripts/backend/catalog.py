import json
import re

import requests
from bs4 import BeautifulSoup

from .camera_specs import CAMERA_SPECS

URL = "https://shopusa.fujifilm-x.com/refurbished/refurbished-cameras/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


class CatalogFetchError(RuntimeError):
    """Raised when the Fujifilm catalog cannot be fetched or parsed."""


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


def _hardcoded_specs(camera_name, max_specs=5):
    entries = CAMERA_SPECS.get(camera_name, [])
    specs = [{"key": key, "value": value} for key, value in entries if key and value]
    return specs[:max_specs]


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


def snapshot_for_camera(camera_name, offers, variant_by_sku, image_cache):
    product_url = next((o.get("url", "") for o in offers if o.get("url")), "")
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

    fallback_image = ""
    for r in rows + all_rows:
        candidate = str(r.get("image_url", "")).strip()
        if candidate:
            fallback_image = candidate
            break

    return {
        "refurb_in_stock": len(skus) > 0,
        "skus": skus,
        "options": rows,
        "all_options": all_rows,
        "available_colors": available_colors,
        "available_styles": available_styles,
        "product_url": product_url,
        "image_url": fallback_image,
        "specs": _hardcoded_specs(camera_name, max_specs=5),
    }


def fetch_catalog():
    try:
        response = requests.get(URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise CatalogFetchError(
            "Unable to fetch Fujifilm refurb catalog. Check your internet or try again."
        ) from exc
    soup = BeautifulSoup(response.text, "html.parser")
    products_by_name = load_item_list_products(soup)
    variant_by_sku = load_variant_details_by_sku(response.text)
    if not products_by_name:
        raise CatalogFetchError(
            "Catalog loaded but no camera listings were found. The site layout may have changed."
        )
    return products_by_name, variant_by_sku
