import os

import requests

from .alerts import build_alert_lines

DEFAULT_AI_MODELS = {
    "claude": "claude-3-5-sonnet-latest",
    "chatgpt": "gpt-4o-mini",
}


def build_ai_placeholder(changes_by_camera):
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


def _normalize_provider(provider_value):
    raw = (provider_value or "").strip().lower()
    if raw in {"openai", "chatgpt", "gpt", "gpt-api"}:
        return "chatgpt"
    if raw in {"anthropic", "claude", "claude-api"}:
        return "claude"
    return "claude"


def resolve_ai_settings(provider=None, model=None):
    resolved_provider = _normalize_provider(provider or os.getenv("AI_PROVIDER", "claude"))
    resolved_model = (model or os.getenv("AI_MODEL", "")).strip()
    if not resolved_model:
        resolved_model = DEFAULT_AI_MODELS[resolved_provider]

    if resolved_provider == "claude":
        api_key = (
            os.getenv("CLAUDE_API_KEY", "").strip()
            or os.getenv("ANTHROPIC_API_KEY", "").strip()
        )
    else:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()

    return {
        "provider": resolved_provider,
        "model": resolved_model,
        "api_key_configured": bool(api_key),
        "api_key": api_key,
    }


def _camera_context_lines(selected_cameras, current):
    lines = []
    for camera in selected_cameras:
        snap = current.get(camera, {})
        in_stock = bool(snap.get("refurb_in_stock"))
        options = snap.get("options") or []
        prices = [float(o["price"]) for o in options if isinstance(o.get("price"), (int, float))]
        min_price = f"${min(prices):,.2f}" if prices else "N/A"
        specs = snap.get("specs") or []
        spec_bits = []
        for spec in specs[:3]:
            key = str(spec.get("key", "")).strip()
            value = str(spec.get("value", "")).strip()
            if key and value:
                spec_bits.append(f"{key}: {value}")
        spec_text = "; ".join(spec_bits) if spec_bits else "No spec data"
        lines.append(
            f"- {camera}: {'In Stock' if in_stock else 'Out of Stock'}, "
            f"in-stock SKU count={len(snap.get('skus', []))}, lowest in-stock price={min_price}. "
            f"Specs: {spec_text}"
        )
    return lines


def _build_llm_prompt(question, selected_cameras, current):
    in_stock = [c for c in selected_cameras if current.get(c, {}).get("refurb_in_stock")]
    context_lines = _camera_context_lines(selected_cameras, current)
    return (
        "You are helping a buyer choose among Fujifilm refurbished cameras.\n"
        "Only use the provided context. If data is missing, state that clearly.\n"
        "Keep answer concise (4-8 bullets max) and practical.\n\n"
        f"Question: {question.strip()}\n\n"
        f"In-stock cameras right now ({len(in_stock)}): "
        + (", ".join(in_stock) if in_stock else "None")
        + "\n\nTracked camera context:\n"
        + "\n".join(context_lines)
    )


def _call_claude_api(api_key, model, system_prompt, user_prompt):
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 450,
            "temperature": 0.3,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    parts = payload.get("content", [])
    text_parts = [part.get("text", "") for part in parts if part.get("type") == "text"]
    return "\n".join([t for t in text_parts if t]).strip()


def _call_chatgpt_api(api_key, model, system_prompt, user_prompt):
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    choices = payload.get("choices", [])
    if not choices:
        return ""
    return str(choices[0].get("message", {}).get("content", "")).strip()


def ask_ai_about_stock(question, selected_cameras, current, provider=None, model=None):
    user_question = (question or "").strip()
    if not user_question:
        return {
            "ok": False,
            "provider": _normalize_provider(provider),
            "model": model or "",
            "message": "Please enter a question first.",
        }

    settings = resolve_ai_settings(provider=provider, model=model)
    if not settings["api_key_configured"]:
        env_key = "CLAUDE_API_KEY/ANTHROPIC_API_KEY" if settings["provider"] == "claude" else "OPENAI_API_KEY"
        return {
            "ok": False,
            "provider": settings["provider"],
            "model": settings["model"],
            "message": f"Missing API key for {settings['provider']}. Set {env_key} in your .env file.",
        }

    system_prompt = (
        "You are Fuji Watch AI, a shopping assistant for refurbished Fujifilm cameras. "
        "Ground every answer in provided stock/spec context only. "
        "If comparing options, be explicit about tradeoffs and uncertainty."
    )
    user_prompt = _build_llm_prompt(user_question, selected_cameras, current)
    try:
        if settings["provider"] == "claude":
            answer = _call_claude_api(settings["api_key"], settings["model"], system_prompt, user_prompt)
        else:
            answer = _call_chatgpt_api(settings["api_key"], settings["model"], system_prompt, user_prompt)
    except requests.RequestException as exc:
        return {
            "ok": False,
            "provider": settings["provider"],
            "model": settings["model"],
            "message": f"API request failed: {exc}",
        }

    if not answer:
        return {
            "ok": False,
            "provider": settings["provider"],
            "model": settings["model"],
            "message": "AI API returned an empty response.",
        }

    return {
        "ok": True,
        "provider": settings["provider"],
        "model": settings["model"],
        "message": answer,
    }
