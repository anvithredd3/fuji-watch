import pandas as pd
import streamlit as st
from streamlit_calendar import calendar
import streamlit.components.v1 as components
from datetime import datetime

from checker import (
    CAMERA_SPECS,
    DEFAULT_SELECTED_CAMERAS,
    get_available_cameras,
    get_last_selected_cameras,
    run_check,
)

TE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Mono', monospace !important;
    background-color: #F2EFE6 !important;
    color: #1A1A18 !important;
}

.block-container { padding-top: 2rem !important; max-width: 860px !important; }

h1 { font-size: 1.1rem !important; font-weight: 500 !important;
     letter-spacing: 0.12em !important; text-transform: uppercase !important; }
h2, h3 { font-size: 0.8rem !important; font-weight: 500 !important;
          letter-spacing: 0.1em !important; text-transform: uppercase !important;
          color: #888880 !important; margin-top: 2rem !important; }

h1::after {
    content: ''; display: block; margin-top: 0.5rem;
    border-bottom: 1px solid #1A1A18;
}

div.stButton > button[kind="primary"] {
    background: #E84C00 !important;
    color: #F2EFE6 !important;
    border: none !important;
    border-radius: 0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.72rem !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    padding: 0.5rem 1.4rem !important;
}
div.stButton > button[kind="primary"]:hover {
    background: #C43D00 !important;
}

div.stButton > button {
    background: transparent !important;
    border: 1px solid #1A1A18 !important;
    border-radius: 0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.72rem !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    color: #1A1A18 !important;
}

.stDataFrame { border: 1px solid #1A1A18 !important; border-radius: 0 !important; }
.stDataFrame, .stDataFrame * {
    font-family: 'IBM Plex Mono', monospace !important;
}
div[data-testid="stDataFrame"] table,
div[data-testid="stDataFrame"] th,
div[data-testid="stDataFrame"] td {
    font-family: 'IBM Plex Mono', monospace !important;
}

.stCaption { font-size: 0.68rem !important; color: #888880 !important;
             letter-spacing: 0.06em !important; }

[data-testid="stMetric"] {
    background: #EAE7DD !important;
    border: 1px solid #CCCAB8 !important;
    padding: 0.75rem 1rem !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.65rem !important; letter-spacing: 0.1em !important;
    text-transform: uppercase !important; color: #888880 !important;
}
[data-testid="stMetricValue"] { font-size: 1.25rem !important; font-weight: 500 !important; }

/* Sidebar typography consistency */
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div {
    font-family: 'IBM Plex Mono', monospace !important;
}
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    font-size: 0.72rem !important;
    letter-spacing: 0.10em !important;
    text-transform: uppercase !important;
    color: #888880 !important;
}
</style>
"""


def _build_summary_rows(current, selected_cameras):
    rows = []
    for camera in selected_cameras:
        snap = current[camera]
        rows.append(
            {
                "Camera": camera,
                "Refurbished Status": "In Stock" if snap["refurb_in_stock"] else "Out of Stock",
                "In-Stock Refurb SKU Count": len(snap["skus"]),
            }
        )
    return rows


def _render_camera_cards(current, target_cameras, muted=False):
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
    # Prompt 1: dynamic baseline height (3 cols, 600px per row + 100px padding).
    card_count = len(cards)
    columns = 2
    rows = max(1, (card_count + columns - 1) // columns)
    dynamic_height = rows * 500
    components.html(grid_html, height=dynamic_height, scrolling=False)


def _build_calendar_events(history_timestamps):
    unique_dates = set()
    for ts in history_timestamps:
        if not isinstance(ts, str):
            continue
        try:
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                local_dt = dt
            else:
                local_dt = dt.astimezone()
            unique_dates.add(local_dt.date().isoformat())
        except ValueError:
            # Fallback for unexpected timestamp formats.
            if "T" in ts:
                unique_dates.add(ts.split("T", 1)[0])
    unique_dates = sorted(unique_dates)
    return [
        {
            "title": "Checked",
            "start": day,
            "allDay": True,
            "backgroundColor": "#16a34a",
            "borderColor": "#16a34a",
            "textColor": "#ffffff",
        }
        for day in unique_dates
    ]


def _status_change_type(text):
    if "BACK IN STOCK" in text:
        return "in_stock"
    if "NOW OUT OF STOCK" in text:
        return "out_of_stock"
    return None


def _build_ai_placeholder_response(question, in_stock_cameras, current):
    q = (question or "").strip()
    if not q:
        return "Ask about current stock, pricing, or which camera might fit your use case."

    if not in_stock_cameras:
        return "No cameras are currently in stock. Try asking me to compare tracked models while we wait."

    # Simple placeholder logic for now; this will be replaced by a real API call later.
    if "video" in q.lower():
        return (
            f"From current stock, {in_stock_cameras[0]} is a strong starter choice for video. "
            "Use the card specs and feature badges (IBIS/EVF) as quick filters."
        )
    if "budget" in q.lower() or "cheap" in q.lower() or "price" in q.lower():
        prices = []
        for cam in in_stock_cameras:
            options = current.get(cam, {}).get("options", [])
            if options and isinstance(options[0].get("price"), (int, float)):
                prices.append((cam, float(options[0]["price"])))
        if prices:
            cam, price = sorted(prices, key=lambda x: x[1])[0]
            return f"Lowest in-stock price right now appears to be {cam} at ${price:,.2f}."
    return (
        f"Currently {len(in_stock_cameras)} cameras are in stock: "
        + ", ".join(in_stock_cameras[:6])
        + ("" if len(in_stock_cameras) <= 6 else ", ...")
        + "."
    )


def _render_ai_placeholder(result):
    active_cameras = result.get("selected_cameras", [])
    current = result.get("current", {})
    in_stock_cameras = [c for c in active_cameras if current.get(c, {}).get("refurb_in_stock")]
    checked_at = result.get("checked_at", "")
    checked_label = checked_at[11:16] if isinstance(checked_at, str) and len(checked_at) >= 16 else "--:--"

    if "ai_messages" not in st.session_state:
        intro = (
            f"I have access to today's refurbished stock. "
            f"Currently {len(in_stock_cameras)} cameras are in stock"
        )
        if in_stock_cameras:
            intro += " including " + ", ".join(in_stock_cameras[:5]) + "."
        else:
            intro += "."
        intro += " Ask me anything."
        st.session_state["ai_messages"] = [("claude", intro)]

    st.subheader("Ask Claude - Placeholder")
    st.caption("Powered by Anthropic API (UI placeholder only, no live API call yet)")

    with st.container(border=True):
        st.markdown("**FUJI WATCH AI**")
        for role, content in st.session_state["ai_messages"][-4:]:
            label = "YOU" if role == "you" else "CLAUDE"
            if role == "you":
                st.markdown(f"<div style='text-align:right;color:#666'>{label}</div>", unsafe_allow_html=True)
                st.markdown(
                    f"<div style='background:#1A1A18;color:#F2EFE6;padding:10px 12px;margin:4px 0 12px 80px;'>{content}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(f"<div style='color:#888'>{label}</div>", unsafe_allow_html=True)
                st.markdown(
                    f"<div style='background:#F2EFE6;border:1px solid #CCCAB8;padding:10px 12px;margin:4px 80px 12px 0;'>{content}</div>",
                    unsafe_allow_html=True,
                )

        col1, col2, col3, col4 = st.columns(4)
        quick_prompts = [
            "Best for video?",
            "Compare top in-stock picks",
            "Worth the refurb price?",
            "Which has no EVF?",
        ]
        for col, prompt in zip([col1, col2, col3, col4], quick_prompts):
            if col.button(prompt, key=f"quick_ai_{prompt}"):
                st.session_state["ai_messages"].append(("you", prompt))
                st.session_state["ai_messages"].append(
                    ("claude", _build_ai_placeholder_response(prompt, in_stock_cameras, current))
                )
                st.rerun()

        question = st.text_input(
            "Ask about current stock...",
            key="ai_placeholder_input",
            placeholder="Ask about current stock...",
            label_visibility="collapsed",
        )
        if st.button("Ask", key="ai_placeholder_ask"):
            prompt = question.strip()
            if prompt:
                st.session_state["ai_messages"].append(("you", prompt))
                st.session_state["ai_messages"].append(
                    ("claude", _build_ai_placeholder_response(prompt, in_stock_cameras, current))
                )
                st.session_state["ai_placeholder_input"] = ""
                st.rerun()

        st.caption(
            f"Context: today's stock, {len(active_cameras)} cameras tracked, last checked {checked_label} local"
        )


st.set_page_config(page_title="Fuji Refurb Watch", layout="wide")
st.markdown(TE_CSS, unsafe_allow_html=True)
st.title("Fuji Refurb Watch")
st.markdown(
    """
This tool checks Fujifilm's refurbished camera catalog and tracks which selected models are in stock right now.
It stores each run locally, highlights changes between checks, and can send Discord alerts when stock status changes.
"""
)

if "available_cameras" not in st.session_state:
    st.session_state["available_cameras"] = get_available_cameras()
available_cameras = st.session_state["available_cameras"]

st.sidebar.markdown("### Camera Selection")
if "selected_cameras_ui" not in st.session_state:
    last_selected = [c for c in get_last_selected_cameras() if c in available_cameras]
    default_selected = (
        last_selected
        or [c for c in DEFAULT_SELECTED_CAMERAS if c in available_cameras]
        or available_cameras
    )
    st.session_state["selected_cameras_ui"] = default_selected
else:
    st.session_state["selected_cameras_ui"] = [
        c for c in st.session_state["selected_cameras_ui"] if c in available_cameras
    ]
    if not st.session_state["selected_cameras_ui"]:
        st.session_state["selected_cameras_ui"] = (
            [c for c in DEFAULT_SELECTED_CAMERAS if c in available_cameras]
            or available_cameras
        )

selected_cameras = st.sidebar.multiselect(
    "Choose cameras to track",
    options=available_cameras,
    default=st.session_state["selected_cameras_ui"],
    key="selected_cameras_ui",
)

if st.sidebar.button("Refresh Camera List"):
    st.session_state["available_cameras"] = get_available_cameras()
    st.rerun()

st.sidebar.markdown("### Discord Settings")
st.sidebar.caption("Control alert delivery and when Discord notifications should be sent.")
discord_notifications = st.sidebar.toggle("discord notifications", value=True)
only_when_change = st.sidebar.toggle("only when change", value=True)

if st.button("Run Fresh Check", type="primary"):
    if not selected_cameras:
        st.warning("Select at least one camera before running a check.")
    else:
        st.session_state["latest_result"] = run_check(
            cameras=selected_cameras,
            discord_notifications=discord_notifications,
            only_when_change=only_when_change,
        )

if "latest_result" not in st.session_state:
    st.info("Click 'Run Fresh Check' to fetch the page and load current status.")
else:
    result = st.session_state["latest_result"]
    active_cameras = result["selected_cameras"]

    st.subheader("Check Metadata")
    checked_time = result["checked_at"][11:16] if result.get("checked_at") else "--:--"
    prev_time = (
        result["previous_checked_at"][11:16]
        if result.get("previous_checked_at")
        else "—"
    )
    in_stock_count = sum(
        1 for cam in active_cameras if result["current"][cam]["refurb_in_stock"]
    )
    col1, col2, col3 = st.columns(3)
    col1.metric("In Stock", f"{in_stock_count} / {len(active_cameras)}")
    col2.metric("Checked at", f"{checked_time} local")
    col3.metric("Prev check", f"{prev_time} local")
    st.markdown(f"Selected cameras: {', '.join(active_cameras)}")
    if result.get("discord_sent"):
        st.success(f"Discord: {result['discord_message']}")
    else:
        st.info(f"Discord: {result.get('discord_message', 'No Discord status available.')}")

    st.subheader("Current Status by Camera")
    summary_df = pd.DataFrame(_build_summary_rows(result["current"], active_cameras))
    summary_df["status_rank"] = summary_df["Refurbished Status"].map(
        {"In Stock": 0, "Out of Stock": 1}
    ).fillna(2)
    summary_df = summary_df.sort_values(
        by=["status_rank", "In-Stock Refurb SKU Count", "Camera"],
        ascending=[True, False, True],
        kind="stable",
    ).drop(columns=["status_rank"])
    # Keep serial numbers sequential after sorting.
    summary_df = summary_df.reset_index(drop=True)
    show_only_in_stock = st.toggle("Show only cameras currently in stock", value=False)
    if show_only_in_stock:
        summary_df = summary_df[summary_df["Refurbished Status"] == "In Stock"]
    
    def _highlight_in_stock(row):
        if row["Refurbished Status"] == "In Stock":
            return ["background-color: rgba(22, 163, 74, 0.20)"] * len(row)
        return [""] * len(row)

    styled_summary = (
        summary_df.style.apply(_highlight_in_stock, axis=1)
        .set_table_styles(
            [
                {
                    "selector": "th",
                    "props": [("font-family", "'IBM Plex Mono', monospace")],
                },
                {
                    "selector": "td",
                    "props": [("font-family", "'IBM Plex Mono', monospace")],
                },
            ]
        )
        .set_properties(**{"font-family": "'IBM Plex Mono', monospace"})
    )

    st.dataframe(styled_summary, use_container_width=True)

    st.subheader("In-Stock Refurbished Options")
    st.markdown("**In-Stock Cameras**")
    in_stock_cameras = [c for c in active_cameras if result["current"][c]["refurb_in_stock"]]
    if in_stock_cameras:
        _render_camera_cards(result["current"], in_stock_cameras, muted=False)
    else:
        st.info("No in-stock cameras to display.")

    st.markdown("**Out-of-Stock Cameras (collapsed)**")
    out_of_stock_cameras = [c for c in active_cameras if not result["current"][c]["refurb_in_stock"]]
    if out_of_stock_cameras:
        with st.expander("Show out-of-stock cameras", expanded=False):
            _render_camera_cards(result["current"], out_of_stock_cameras, muted=True)
    else:
        st.caption("No out-of-stock cameras in current selection.")

    st.subheader("Changes Since Last Run")
    status_changes = []
    for camera in active_cameras:
        lines = [line.strip() for line in result["changes_by_camera"][camera]]
        for line in lines:
            change_type = _status_change_type(line)
            if change_type:
                status_changes.append((camera, line, change_type))

    if not status_changes:
        st.caption("No changes detected.")
    else:
        for camera, line, change_type in status_changes:
            if change_type == "in_stock":
                st.markdown(
                    f"<div style='color:#f59e0b;'>• {camera}: {line}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='color:#9ca3af;'>• {camera}: {line}</div>",
                    unsafe_allow_html=True,
                )

    st.subheader("Check History Calendar")
    events = _build_calendar_events(result.get("history", []))
    if events:
        calendar_options = {
            "initialView": "dayGridMonth",
            "headerToolbar": {
                "left": "prev,next today",
                "center": "title",
                "right": "dayGridMonth,timeGridWeek",
            },
            "height": 650,
        }
        calendar(events=events, options=calendar_options, key="check-history-calendar")
        st.caption("Green highlighted dates are days when a check was run.")
    else:
        st.info("No check history yet. Run a check to populate calendar dates.")

    _render_ai_placeholder(result)
