"""
Webhook endpoints for external communication (Telegram, Slack, Custom Webhooks).
"""

import asyncio
import hashlib
import hmac
import json
import time
from copy import deepcopy
from typing import Any

from fastapi import APIRouter, Request, BackgroundTasks, HTTPException

from src.config.settings import system_config
from src.memory.redis_manager import redis_manager
from src.utils.logger import log
from src.agent.agent_loop import get_agent

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
WEBHOOK_CHANNELS = ("telegram", "slack")


def _empty_channel_metrics() -> dict:
    return {
        "received": 0,
        "accepted": 0,
        "rejected": 0,
        "ignored": 0,
        "processed": 0,
        "failed": 0,
        "last_event_at": None,
        "last_error": None,
    }


_webhook_metrics = {channel: _empty_channel_metrics() for channel in WEBHOOK_CHANNELS}


async def _process_webhook_message(message: str, channel: str, sender_id: str):
    """
    Procesa un mensaje asincronamente usando el agente y despacha la respuesta al canal.
    """
    try:
        log.info(f"Procesando webhook de [{channel}] - Sender: {sender_id}")
        # Asignar un session_id deterministico por usuario de canal
        session_id = f"webhook_{channel}_{sender_id}"

        # Load the agent
        agent = await get_agent(domain="generic", persona="default")
        # Ensure session history is loaded
        agent.session_id = session_id

        # We don't stream here, we just await the final answer
        response_text = await agent.process_user_message(message)

        # Here we would dispatch to the specific channel API (Slack, Telegram, etc)
        # Mocking the dispatch for now
        log.info(
            f"Respuesta generada para [{channel}] {sender_id}: {response_text[:50]}..."
        )
        _record_webhook_metric(channel, "processed")

    except Exception as e:
        _record_webhook_metric(channel, "failed", str(e))
        log.error(f"Error procesando mensaje de webhook ({channel}): {e}")


@router.post("/telegram")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint para recibir actualizaciones de un bot de Telegram.
    """
    _record_webhook_metric("telegram", "received")
    _ensure_webhooks_enabled("telegram")
    try:
        _verify_telegram_secret(request)
    except HTTPException as exc:
        _record_webhook_metric("telegram", "rejected", str(exc.detail))
        raise

    try:
        data = _decode_json(await request.body())
    except ValueError as exc:
        _record_webhook_metric("telegram", "rejected", "Invalid JSON")
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    accepted = False
    # Telegram usually sends message inside data["message"]
    if "message" in data:
        message_data = data["message"]
        text = message_data.get("text", "")
        chat_id = message_data.get("chat", {}).get("id", "")

        if text and chat_id:
            try:
                _ensure_allowed(
                    str(chat_id), system_config.webhook_allowed_telegram_chats
                )
            except HTTPException as exc:
                _record_webhook_metric("telegram", "rejected", str(exc.detail))
                raise
            background_tasks.add_task(
                _process_webhook_message, text, "telegram", str(chat_id)
            )
            _record_webhook_metric("telegram", "accepted")
            accepted = True

    if not accepted:
        _record_webhook_metric("telegram", "ignored")

    return {"status": "ok"}


@router.post("/slack")
async def slack_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint para recibir eventos (Event API) de Slack.
    """
    _record_webhook_metric("slack", "received")
    _ensure_webhooks_enabled("slack")
    raw_body = await request.body()
    try:
        _verify_slack_signature(request, raw_body)
    except HTTPException as exc:
        _record_webhook_metric("slack", "rejected", str(exc.detail))
        raise

    try:
        data = _decode_json(raw_body)
    except ValueError as exc:
        _record_webhook_metric("slack", "rejected", "Invalid JSON")
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    # Slack Event API challenge
    if data.get("type") == "url_verification":
        _record_webhook_metric("slack", "accepted")
        return {"challenge": data.get("challenge")}

    accepted = False
    # Slack actual event
    if "event" in data:
        event = data["event"]
        if event.get("type") == "message" and "bot_id" not in event:
            text = event.get("text", "")
            user_id = event.get("user", "")
            if text and user_id:
                try:
                    _ensure_allowed(
                        str(user_id), system_config.webhook_allowed_slack_users
                    )
                except HTTPException as exc:
                    _record_webhook_metric("slack", "rejected", str(exc.detail))
                    raise
                background_tasks.add_task(
                    _process_webhook_message, text, "slack", str(user_id)
                )
                _record_webhook_metric("slack", "accepted")
                accepted = True

    if not accepted:
        _record_webhook_metric("slack", "ignored")

    return {"status": "ok"}


async def get_webhook_metrics() -> dict[str, Any]:
    """Return shared webhook metrics, falling back to in-process counters."""
    shared_metrics = await redis_manager.get_webhook_metrics(WEBHOOK_CHANNELS)
    channels = (
        shared_metrics if shared_metrics is not None else deepcopy(_webhook_metrics)
    )
    return _build_webhook_metrics_payload(channels)


def _build_webhook_metrics_payload(channels: dict[str, Any]) -> dict[str, Any]:
    """Build total and per-channel webhook metrics payload."""
    totals = {
        "received": 0,
        "accepted": 0,
        "rejected": 0,
        "ignored": 0,
        "processed": 0,
        "failed": 0,
    }
    for metrics in channels.values():
        for key in totals:
            totals[key] += int(metrics.get(key, 0) or 0)
    return {"total": totals, "channels": channels}


def _record_webhook_metric(
    channel: str,
    event: str,
    error: str | None = None,
) -> None:
    """Increment webhook counters without affecting request flow."""
    metrics = _webhook_metrics.setdefault(channel, _empty_channel_metrics())
    if event in metrics and isinstance(metrics[event], int):
        metrics[event] += 1
    metrics["last_event_at"] = time.time()
    if error:
        metrics["last_error"] = error
    _record_shared_webhook_metric(channel, event, error)


def _record_shared_webhook_metric(
    channel: str,
    event: str,
    error: str | None,
) -> None:
    """Best-effort async write of webhook metrics to Redis."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(redis_manager.record_webhook_metric(channel, event, error))


def _reset_webhook_metrics() -> None:
    """Reset webhook metrics for tests."""
    _webhook_metrics.clear()
    _webhook_metrics.update(
        {channel: _empty_channel_metrics() for channel in WEBHOOK_CHANNELS}
    )


def _decode_json(raw_body: bytes) -> dict:
    """Decode a webhook JSON body from already-read bytes."""
    payload = json.loads(raw_body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Webhook payload must be a JSON object")
    return payload


def _ensure_webhooks_enabled(channel: str) -> None:
    """Reject webhook requests when webhooks are disabled by configuration."""
    if not system_config.webhooks_enabled:
        raise HTTPException(status_code=503, detail=f"{channel} webhook disabled")


def _verify_telegram_secret(request: Request) -> None:
    """Validate Telegram secret token when configured."""
    expected_secret = system_config.webhook_telegram_secret
    if not expected_secret:
        if system_config.is_secure_runtime or system_config.webhook_secret_required:
            raise HTTPException(
                status_code=503,
                detail="Telegram webhook disabled until secret is configured",
            )
        return

    provided_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(provided_secret, expected_secret):
        raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret")


def _verify_slack_signature(request: Request, raw_body: bytes) -> None:
    """Validate Slack signing secret and timestamp replay window when configured."""
    signing_secret = system_config.webhook_slack_signing_secret
    if not signing_secret:
        if system_config.is_secure_runtime or system_config.webhook_secret_required:
            raise HTTPException(
                status_code=503,
                detail="Slack webhook disabled until signing secret is configured",
            )
        return

    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if not timestamp or not signature:
        raise HTTPException(status_code=401, detail="Missing Slack signature")

    try:
        request_time = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid Slack timestamp") from exc

    max_skew = max(int(system_config.webhook_slack_max_skew_seconds), 0)
    if abs(int(time.time()) - request_time) > max_skew:
        raise HTTPException(status_code=401, detail="Stale Slack webhook request")

    base_string = b"v0:" + timestamp.encode("utf-8") + b":" + raw_body
    expected = (
        "v0="
        + hmac.new(
            signing_secret.encode("utf-8"),
            base_string,
            hashlib.sha256,
        ).hexdigest()
    )
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")


def _ensure_allowed(identity: str, allowed_csv: str) -> None:
    """Reject webhook senders outside an optional comma-separated allowlist."""
    allowed = {item.strip() for item in allowed_csv.split(",") if item.strip()}
    if allowed and identity not in allowed:
        raise HTTPException(status_code=403, detail="Webhook sender not allowed")
