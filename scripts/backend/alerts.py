import os

import requests


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
