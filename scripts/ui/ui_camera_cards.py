import streamlit.components.v1 as components

from scripts.backend.camera_specs import CAMERA_SPECS


def render_camera_cards(current, target_cameras, muted=False):
    def _spec_value(specs, wanted_key):
        wanted = wanted_key.lower()
        for spec in specs:
            key = spec.get("key", "").strip().lower()
            if key == wanted:
                return spec.get("value", "").strip()
        return ""

    def _yes_no_badge(value):
        txt = (value or "").strip().lower()
        return "Yes" if txt.startswith("yes") else "No"

    def _hardcoded_spec(camera_name, wanted_key):
        entries = CAMERA_SPECS.get(camera_name, [])
        wanted = wanted_key.strip().lower()
        for key, value in entries:
            if str(key).strip().lower() == wanted:
                return str(value).strip()
        return ""

    def _color_dot_html(color):
        label = (color or "").strip().lower()
        if "silver" in label:
            fill = "#C7C7C7"
        elif "black" in label:
            fill = "#1A1A18"
        else:
            return ""
        return f'<span title="{color}" style="width:8px;height:8px;border-radius:999px;background:{fill};border:1px solid #7F7F7A;display:inline-block;"></span>'

    placeholder_svg = """
    <div style="width:100%;height:180px;background:#FFFFFF;border-bottom:1px solid #CCCAB8;
                display:flex;align-items:center;justify-content:center;position:relative;">
      <svg width="42" height="42" viewBox="0 0 24 24" fill="none"
           stroke="#1A1A18" stroke-width="1.2" opacity="0.25">
        <rect x="2" y="6" width="20" height="14" rx="1"/>
        <circle cx="12" cy="13" r="3.5"/>
        <path d="M8 6V5a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v1"/>
      </svg>
    </div>
    """

    cards = []
    for cam in target_cameras:
        snap = current[cam]
        in_stock = bool(snap.get("refurb_in_stock"))
        first_opt = (snap.get("options") or [{}])[0]
        price = first_opt.get("price")
        sku = first_opt.get("sku", "")
        in_stock_options = snap.get("options") or []
        all_options = snap.get("all_options") or snap.get("options") or []
        colors = sorted(
            {
                str(o.get("color", "")).strip()
                for o in in_stock_options
                if str(o.get("color", "")).strip()
                and str(o.get("color", "")).strip().lower() != "unknown"
            }
        )
        styles = sorted(
            {
                str(o.get("style", "")).strip()
                for o in in_stock_options
                if str(o.get("style", "")).strip()
                and str(o.get("style", "")).strip().lower() != "unknown"
            }
        )
        styles = [s for s in styles if s and s.strip() and s.strip().lower() != "unknown"]
        if not in_stock:
            colors = []
            styles = []

        preferred_image = ""
        first_in_stock_color = ""
        if in_stock_options:
            first_in_stock_color = str(in_stock_options[0].get("color", "")).lower()
        if "silver" in first_in_stock_color:
            for opt in in_stock_options:
                image_candidate = str(opt.get("image_url", "")).strip()
                if image_candidate and "silver" in image_candidate.lower():
                    preferred_image = image_candidate
                    break
        if not preferred_image:
            for opt in in_stock_options:
                image_candidate = str(opt.get("image_url", "")).strip()
                if image_candidate:
                    preferred_image = image_candidate
                    break
        if not preferred_image:
            for opt in all_options:
                image_candidate = str(opt.get("image_url", "")).strip()
                if image_candidate:
                    preferred_image = image_candidate
                    break
        image_url = preferred_image or snap.get("image_url", "")
        product_url = snap.get("product_url", "")
        specs = snap.get("specs", [])
        spec_rows = [
            ("Image Sensor", _spec_value(specs, "Image Sensor")),
            ("Processor", _spec_value(specs, "Image Processing Engine")),
            ("LCD Monitor", _spec_value(specs, "LCD Monitor")),
        ]
        evf_value = _yes_no_badge(_hardcoded_spec(cam, "EVF"))
        ibis_value = _yes_no_badge(_hardcoded_spec(cam, "IBIS"))
        ws_value = _yes_no_badge(_hardcoded_spec(cam, "Weather Sealed"))
        color_dots = "".join(_color_dot_html(c) for c in colors)
        if color_dots:
            color_dots = (
                '<div style="position:absolute;right:8px;bottom:8px;display:flex;gap:5px;">'
                + color_dots
                + "</div>"
            )

        opacity = "0.45" if muted else "1"
        badge = (
            '<span style="background:#E84C00;color:#F2EFE6;font-size:0.52rem;'
            'letter-spacing:0.1em;text-transform:uppercase;padding:3px 7px;'
            'font-weight:500;white-space:nowrap;">IN STOCK</span>'
            if in_stock
            else
            '<span style="background:#CCCAB8;color:#888880;font-size:0.52rem;'
            'letter-spacing:0.1em;text-transform:uppercase;padding:3px 7px;'
            'white-space:nowrap;">OUT OF STOCK</span>'
        )

        if image_url:
            image_block = f"""
            <div style="width:100%;height:180px;background:#FFFFFF;border-bottom:1px solid #CCCAB8;
                        display:flex;align-items:center;justify-content:center;overflow:hidden;position:relative;">
              <img src="{image_url}" style="width:100%;height:100%;object-fit:contain;padding:8px;" />
              {color_dots}
            </div>
            """
        else:
            image_block = placeholder_svg.replace("</div>", f"{color_dots}</div>", 1)

        specs_html = ""
        for key, value in spec_rows:
            if not value:
                continue
            specs_html += (
                f'<div style="display:flex;justify-content:space-between;padding:2px 0;">'
                f'<span style="font-size:0.58rem;color:#888880;">{key}</span>'
                f'<span style="font-size:0.58rem;font-weight:500;max-width:55%;text-align:right;">{value}</span>'
                f"</div>"
            )
        variant_pills = ""
        for c in colors[:2]:
            variant_pills += (
                '<span style="padding:2px 8px;border-radius:999px;font-size:0.54rem;'
                f'border:1px solid #A7A495;background:#F2EFE6;color:#1A1A18;">Color: {c}</span>'
            )
        for s in styles[:2]:
            variant_pills += (
                '<span style="padding:2px 8px;border-radius:999px;font-size:0.54rem;'
                f'border:1px solid #A7A495;background:#F2EFE6;color:#1A1A18;">Style: {s}</span>'
            )
        feature_badges = ""
        for label, val in [("EVF", evf_value), ("IBIS", ibis_value), ("Weather Sealed", ws_value)]:
            bg = "#1A1A18" if val == "Yes" else "#B8B5A9"
            fg = "#F2EFE6" if val == "Yes" else "#5C5A52"
            text = label if val == "Yes" else f"No {label}"
            feature_badges += (
                f'<span style="padding:4px 7px;border-radius:3px;background:{bg};color:{fg};'
                f'font-size:0.52rem;letter-spacing:0.02em;">{text}</span>'
            )

        price_block = (
            f'<div style="font-size:1.0rem;font-weight:500;margin-bottom:0.45rem;">${float(price):,.2f}</div>'
            if in_stock and isinstance(price, (int, float))
            else ""
        )
        sku_block = (
            f'<div style="font-size:0.55rem;color:#888880;margin-top:0.5rem;">SKU: {sku}</div>'
            if in_stock and sku
            else ""
        )
        button_block = (
            f'<a href="{product_url}" target="_blank" '
            f'style="display:block;width:calc(100% - 8px);margin:0.65rem auto 0 auto;background:transparent;'
            f'border:1px solid #1A1A18;font-family:\'IBM Plex Mono\',monospace;'
            f'font-size:0.56rem;letter-spacing:0.09em;text-transform:uppercase;'
            f'padding:0.35rem;text-align:center;color:#1A1A18;text-decoration:none;">'
            f'View on Fujifilm →</a>'
            if in_stock and product_url and not muted
            else ""
        )

        cards.append(
            f"""
            <div style="background:#DCD8CB;border:1px solid #CCCAB8;opacity:{opacity};
                        min-height:480px;
                        display:flex;flex-direction:column;">
              {image_block}
              <div style="padding:0.75rem 0.85rem;display:flex;flex-direction:column;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.45rem;">
                  <span style="font-size:0.78rem;font-weight:500;letter-spacing:0.06em;text-transform:uppercase;">{cam}</span>
                  {badge}
                </div>
                {price_block}
                <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:0.45rem;">{variant_pills}</div>
                <div style="border-top:1px solid #CCCAB8;padding-top:0.4rem;">{specs_html}</div>
                {sku_block}
                <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:0.55rem;">{feature_badges}</div>
                {button_block}
              </div>
            </div>
            """
        )

    grid_html = (
        "<div id=\"card-grid\" "
        "style=\"display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));"
        "gap:12px;font-family:'IBM Plex Mono',monospace;\">"
        + "".join(cards)
        + "</div>"
        "<script>"
        "(function(){"
        "  function setFrameHeight(){"
        "    var h = Math.max("
        "      document.body.scrollHeight,"
        "      document.documentElement.scrollHeight"
        "    );"
        "    if (window.parent) {"
        "      window.parent.postMessage({"
        "        isStreamlitMessage: true,"
        "        type: 'streamlit:setFrameHeight',"
        "        height: h + 16"
        "      }, '*');"
        "    }"
        "  }"
        "  window.addEventListener('load', setFrameHeight);"
        "  window.addEventListener('resize', setFrameHeight);"
        "  var ro = new ResizeObserver(setFrameHeight);"
        "  ro.observe(document.body);"
        "  setTimeout(setFrameHeight, 50);"
        "  setTimeout(setFrameHeight, 250);"
        "})();"
        "</script>"
    )
    card_count = len(cards)
    columns = 2
    rows = max(1, (card_count + columns - 1) // columns)
    dynamic_height = rows * 500
    components.html(grid_html, height=dynamic_height, scrolling=False)
