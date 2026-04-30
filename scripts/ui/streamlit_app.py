import pandas as pd
import streamlit as st
from streamlit_calendar import calendar
from datetime import datetime
import html
import re

from scripts.checker import (
    DEFAULT_SELECTED_CAMERAS,
    DEFAULT_AI_MODELS,
    ask_ai_about_stock,
    get_available_cameras,
    get_last_selected_cameras,
    resolve_ai_settings,
    run_check,
)
from scripts.backend.catalog import CatalogFetchError, URL
from scripts.ui.ui_camera_cards import render_camera_cards

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

.ai-chat-window {
    border: 1px solid #CCCAB8;
    background: #ECE8DD;
    padding: 10px 12px;
    overflow-y: auto;
}
.ai-chat-window.compact {
    max-height: clamp(220px, 36vh, 320px);
}
.ai-chat-window.expanded {
    max-height: clamp(260px, 52vh, 520px);
}
.ai-chat-label-you {
    text-align: right;
    color: #666;
    margin: 3px 0;
    font-size: 0.62rem;
    letter-spacing: 0.08em;
}
.ai-chat-label-assistant {
    color: #888;
    margin: 3px 0;
    font-size: 0.62rem;
    letter-spacing: 0.08em;
}
.ai-chat-bubble-you {
    background: #1A1A18;
    color: #F2EFE6;
    padding: 10px 12px;
    margin: 4px 0 12px 90px;
    white-space: pre-wrap;
    line-height: 1.45;
}
.ai-chat-bubble-assistant {
    background: #F2EFE6;
    border: 1px solid #CCCAB8;
    color: #1A1A18;
    padding: 10px 12px;
    margin: 4px 90px 12px 0;
    white-space: pre-wrap;
    line-height: 1.45;
}
@media (max-width: 768px) {
    .ai-chat-window.compact {
        max-height: clamp(210px, 42vh, 360px);
    }
    .ai-chat-window.expanded {
        max-height: clamp(240px, 58vh, 520px);
    }
    .ai-chat-bubble-you {
        margin-left: 28px;
    }
    .ai-chat-bubble-assistant {
        margin-right: 28px;
    }
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
    render_camera_cards(current, target_cameras, muted=muted)


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


def _render_ai_assistant(result):
    active_cameras = result.get("selected_cameras", [])
    current = result.get("current", {})
    in_stock_cameras = [c for c in active_cameras if current.get(c, {}).get("refurb_in_stock")]
    checked_at = result.get("checked_at", "")
    checked_label = checked_at[11:16] if isinstance(checked_at, str) and len(checked_at) >= 16 else "--:--"
    provider = st.session_state.get("ai_provider", "claude")
    model = st.session_state.get("ai_model", DEFAULT_AI_MODELS.get(provider, ""))
    reasoning_style = st.session_state.get("ai_reasoning_style", "balanced")
    assistant_label = "CLAUDE" if provider == "claude" else "CHATGPT"
    chat_mode = st.session_state.get("ai_chat_mode", "Compact")

    if "ai_messages" not in st.session_state:
        intro = (
            f"I have access to today's refurbished stock. "
            f"Currently {len(in_stock_cameras)} cameras are in stock"
        )
        if in_stock_cameras:
            intro += " including " + ", ".join(in_stock_cameras[:5]) + "."
        else:
            intro += "."
        intro += " Ask me anything about value, specs, video, travel, or budget."
        st.session_state["ai_messages"] = [("assistant", intro)]
    if "ai_pending_prompt" not in st.session_state:
        st.session_state["ai_pending_prompt"] = ""

    st.subheader("Ask AI")
    st.caption(f"Provider: {provider} | Model: {model}")

    def _run_ai_request(prompt_text):
        st.session_state["ai_messages"].append(("you", prompt_text))
        st.session_state["ai_messages"].append(("assistant", "Thinking..."))
        st.session_state["ai_pending_prompt"] = prompt_text
        st.rerun()

    def _format_chat_html(text):
        safe = html.escape(str(text or ""))
        safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
        safe = safe.replace("\n", "<br>")
        return safe

    pending_prompt = (st.session_state.get("ai_pending_prompt") or "").strip()
    if pending_prompt:
        with st.spinner("Thinking..."):
            answer = ask_ai_about_stock(
                question=pending_prompt,
                selected_cameras=active_cameras,
                current=current,
                provider=provider,
                model=model,
                reasoning_style=reasoning_style,
            )
        if st.session_state["ai_messages"] and st.session_state["ai_messages"][-1][0] == "assistant":
            st.session_state["ai_messages"][-1] = ("assistant", answer["message"])
        else:
            st.session_state["ai_messages"].append(("assistant", answer["message"]))
        st.session_state["ai_pending_prompt"] = ""
        st.rerun()

    def _append_ai_answer(prompt_text):
        _run_ai_request(prompt_text)

    with st.container(border=True):
        st.markdown("**FUJI WATCH AI**")
        visible_pairs = 6 if chat_mode == "Compact" else 14
        render_messages = st.session_state["ai_messages"][-visible_pairs:]
        message_html_parts = []
        for role, content in render_messages:
            safe_content = _format_chat_html(content)
            if role == "you":
                message_html_parts.append("<div class='ai-chat-label-you'>YOU</div>")
                message_html_parts.append(f"<div class='ai-chat-bubble-you'>{safe_content}</div>")
            else:
                message_html_parts.append(f"<div class='ai-chat-label-assistant'>{assistant_label}</div>")
                message_html_parts.append(f"<div class='ai-chat-bubble-assistant'>{safe_content}</div>")
        window_class = "compact" if chat_mode == "Compact" else "expanded"
        st.markdown(
            f"<div class='ai-chat-window {window_class}'>" + "".join(message_html_parts) + "</div>",
            unsafe_allow_html=True,
        )

        with st.form("ai_prompt_form", clear_on_submit=True):
            question = st.text_input(
                "Ask about current stock...",
                key="ai_placeholder_input",
                placeholder="Ask about current stock...",
                label_visibility="collapsed",
            )
            asked = st.form_submit_button("Ask")
        if asked:
            prompt = question.strip()
            if prompt:
                _append_ai_answer(prompt)

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

st.sidebar.markdown("### AI Settings")
default_ai = resolve_ai_settings()
provider_options = [("Claude", "claude"), ("ChatGPT", "chatgpt")]
provider_label_to_value = {label: value for label, value in provider_options}
provider_value_to_label = {value: label for label, value in provider_options}
default_provider = st.session_state.get("ai_provider", default_ai["provider"])
selected_provider_label = st.sidebar.selectbox(
    "provider",
    options=[label for label, _ in provider_options],
    index=[label for label, value in provider_options].index(
        provider_value_to_label.get(default_provider, "Claude")
    ),
)
selected_provider = provider_label_to_value[selected_provider_label]
st.session_state["ai_provider"] = selected_provider

model_default_for_provider = (
    default_ai["model"] if selected_provider == default_ai["provider"] else DEFAULT_AI_MODELS[selected_provider]
)
if st.session_state.get("ai_model_provider") != selected_provider:
    st.session_state["ai_model"] = model_default_for_provider
    st.session_state["ai_model_provider"] = selected_provider
st.session_state["ai_model"] = st.sidebar.text_input(
    "model",
    value=st.session_state.get("ai_model", model_default_for_provider),
    help="Examples: claude-3-5-sonnet-latest, gpt-4o-mini, gpt-4.1",
)
st.session_state["ai_reasoning_style"] = st.sidebar.selectbox(
    "reasoning style",
    options=["concise", "balanced", "deep"],
    index=["concise", "balanced", "deep"].index(
        st.session_state.get("ai_reasoning_style", "balanced")
        if st.session_state.get("ai_reasoning_style", "balanced") in {"concise", "balanced", "deep"}
        else "balanced"
    ),
    help="Controls response depth and level of tradeoff detail.",
)
st.session_state["ai_chat_mode"] = st.sidebar.radio(
    "chat panel",
    options=["Compact", "Expanded"],
    index=0 if st.session_state.get("ai_chat_mode", "Compact") == "Compact" else 1,
    horizontal=True,
)

if st.button("Run Fresh Check", type="primary"):
    if not selected_cameras:
        st.warning("Select at least one camera before running a check.")
    else:
        try:
            st.session_state["latest_result"] = run_check(
                cameras=selected_cameras,
                discord_notifications=discord_notifications,
                only_when_change=only_when_change,
            )
        except CatalogFetchError as exc:
            st.error(
                f"{exc} Source: {URL}"
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

    _render_ai_assistant(result)
