import pandas as pd
import streamlit as st
from streamlit_calendar import calendar
from datetime import datetime

from checker import (
    DEFAULT_SELECTED_CAMERAS,
    get_available_cameras,
    get_last_selected_cameras,
    run_check,
)


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


def _build_option_rows(current, selected_cameras):
    rows = []
    for camera in selected_cameras:
        for opt in current[camera]["options"]:
            rows.append(
                {
                    "Camera": camera,
                    "SKU": opt["sku"],
                    "Color": opt["color"],
                    "Style": opt["style"],
                    "Price": opt["price"],
                    "URL": opt["url"],
                }
            )
    return rows


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


st.set_page_config(page_title="Fuji Refurb Watch", layout="wide")
st.title("Fuji Refurb Watch")
st.caption("Method 1: BeautifulSoup + JSON-LD parsing from refurbished listing page")

if "available_cameras" not in st.session_state:
    st.session_state["available_cameras"] = get_available_cameras()
available_cameras = st.session_state["available_cameras"]

st.sidebar.header("Camera Selection")
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

st.sidebar.header("Discord Settings")
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
    st.write(f"Checked at (Local): `{result['checked_at']}`")
    if result["previous_checked_at"]:
        st.write(f"Previous check (Local): `{result['previous_checked_at']}`")
    else:
        st.write("Previous check: `(none)`")
    st.write(f"Selected cameras: `{', '.join(active_cameras)}`")
    mode = result.get("discord_mode", {})
    st.write(
        "Discord mode: "
        f"`notifications={mode.get('notifications', True)}`, "
        f"`only_when_change={mode.get('only_when_change', True)}`"
    )
    if result.get("discord_sent"):
        st.success(f"Discord: {result['discord_message']}")
    else:
        st.info(f"Discord: {result.get('discord_message', 'No Discord status available.')}")

    st.subheader("Current Status by Camera")
    summary_df = pd.DataFrame(_build_summary_rows(result["current"], active_cameras))
    show_only_in_stock = st.toggle("Show only cameras currently in stock", value=False)
    if show_only_in_stock:
        summary_df = summary_df[summary_df["Refurbished Status"] == "In Stock"]
    
    def _highlight_in_stock(row):
        if row["Refurbished Status"] == "In Stock":
            return ["background-color: rgba(22, 163, 74, 0.20)"] * len(row)
        return [""] * len(row)

    st.dataframe(
        summary_df.style.apply(_highlight_in_stock, axis=1),
        use_container_width=True,
    )

    st.subheader("In-Stock Refurbished Options")
    option_rows = _build_option_rows(result["current"], active_cameras)
    if option_rows:
        options_df = pd.DataFrame(option_rows)
        st.dataframe(
            options_df,
            use_container_width=True,
            column_config={"URL": st.column_config.LinkColumn("URL")},
        )
    else:
        st.warning("No refurbished options are currently in stock for selected cameras.")

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
