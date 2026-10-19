"""Default-deny, action-bound human confirmation for the upstream controller."""

import asyncio
import hashlib
import inspect
import json
import secrets
from urllib.parse import urlsplit, urlunsplit


def redact(value, key=""):
    if any(word in key.lower() for word in ("password", "token", "secret", "text", "value")):
        return "[redacted]"
    if isinstance(value, dict):
        return {k: redact(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, key) for v in value]
    if isinstance(value, str) and value.startswith(("https://", "http://")):
        url = urlsplit(value)
        return urlunsplit((url.scheme, url.hostname or "", url.path, "", ""))
    return value


async def authorize_action(name, params, callback, browser=None):
    if name in {"done", "ask_for_assistant"}:
        return True
    if callback is None:
        return False
    serialized = json.dumps([name, params], sort_keys=True, ensure_ascii=False)
    if len(serialized.encode()) > 16384:
        return False
    digest = hashlib.sha256((secrets.token_hex(16) + serialized).encode()).hexdigest()
    prompt = (
        f"Approve one browser action: {name}\n"
        f"Parameters (sensitive fields hidden): {json.dumps(redact(params), ensure_ascii=False)}\n"
        f"Reply exactly APPROVE {digest} to allow this action once. Otherwise it is denied."
    )
    try:
        # The upstream callback may be synchronous or asynchronous.
        if inspect.iscoroutinefunction(callback):
            reply = await asyncio.wait_for(callback(prompt, browser), timeout=120)
        else:
            reply = await asyncio.wait_for(
                asyncio.to_thread(callback, prompt, browser), timeout=120
            )
            if inspect.isawaitable(reply):
                reply = await asyncio.wait_for(reply, timeout=120)
        return isinstance(reply, dict) and reply.get("response") == f"APPROVE {digest}"
    except Exception:  # noqa: BLE001 - any callback failure must deny the action
        return False
