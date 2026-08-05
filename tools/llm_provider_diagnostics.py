"""Run a redacted OpenAI-compatible Provider network and chat smoke check."""

from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path
from time import perf_counter
from typing import get_args
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.shared.config import LlmProviderConfig, LlmProviderName, settings

SUPPORTED_PROVIDERS = get_args(LlmProviderName)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run network and chat diagnostics for a registered LLM Provider."
    )
    parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default=None)
    parser.add_argument(
        "--chat",
        action="store_true",
        help="send one minimal non-business chat request with SDK retries disabled",
    )
    parser.add_argument("--timeout", type=float, default=None)
    args = parser.parse_args()
    configuration = settings.model_copy(
        update={"llm_provider": args.provider} if args.provider else {}
    )
    provider_config = configuration.llm_provider_config()
    timeout = args.timeout or provider_config.timeout_seconds
    result: dict[str, object] = {
        "configuration": {
            "provider": provider_config.provider,
            "base_url": _safe_base_url(provider_config.base_url),
            "model": provider_config.model or "",
            "timeout_seconds": timeout,
            "api_key_configured": bool(provider_config.api_key),
        },
        "checks": {},
    }

    if not provider_config.api_key:
        result["status"] = "not_configured"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    parsed = urlparse(provider_config.base_url)
    if not parsed.hostname:
        result["status"] = "invalid_base_url"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    checks = result["checks"]
    assert isinstance(checks, dict)
    addresses = _resolve(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    checks["dns"] = {"host": parsed.hostname, "addresses": addresses}
    checks["tcp"] = _tcp_check(
        parsed.hostname,
        parsed.port or (443 if parsed.scheme == "https" else 80),
        timeout,
    )
    checks["https"] = _http_check(provider_config, timeout)
    if args.chat:
        checks["chat"] = _chat_check(provider_config, timeout)

    result["status"] = "ok" if _checks_ok(checks, args.chat) else "failed"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


def _resolve(host: str, port: int) -> list[str]:
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        return sorted({item[4][0] for item in addresses})
    except OSError as exc:
        return [f"error:{type(exc).__name__}:{str(exc)[:200]}"]


def _tcp_check(host: str, port: int, timeout: float) -> dict[str, object]:
    started = perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"ok": True, "duration_ms": round((perf_counter() - started) * 1000, 2)}
    except OSError as exc:
        return {
            "ok": False,
            "duration_ms": round((perf_counter() - started) * 1000, 2),
            "exception_type": type(exc).__name__,
            "message": str(exc)[:300],
        }


def _http_check(configuration: LlmProviderConfig, timeout: float) -> dict[str, object]:
    url = configuration.base_url.rstrip("/") + "/models"
    request = Request(
        url,
        headers={"Authorization": f"Bearer {configuration.api_key}"},
        method="GET",
    )
    started = perf_counter()
    try:
        with urlopen(request, timeout=timeout) as response:
            return {
                "ok": 200 <= response.status < 300,
                "status_code": response.status,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            }
    except HTTPError as exc:
        return {
            "ok": exc.code in {401, 403, 404, 405},
            "status_code": exc.code,
            "duration_ms": round((perf_counter() - started) * 1000, 2),
            "interpretation": "server_reachable_http_error",
        }
    except (URLError, TimeoutError, OSError) as exc:
        return {
            "ok": False,
            "duration_ms": round((perf_counter() - started) * 1000, 2),
            "exception_type": type(exc).__name__,
            "message": str(exc)[:300],
        }


def _chat_check(configuration: LlmProviderConfig, timeout: float) -> dict[str, object]:
    from openai import OpenAI

    started = perf_counter()
    try:
        client = OpenAI(
            api_key=configuration.api_key,
            base_url=configuration.base_url,
            timeout=timeout,
            max_retries=0,
        )
        request_kwargs: dict[str, object] = {
            "model": configuration.model,
            "messages": [{"role": "user", "content": "Reply with exactly OK."}],
            "temperature": 0,
            "max_tokens": 32,
        }
        if configuration.thinking is not None:
            request_kwargs["extra_body"] = {
                "thinking": {"type": configuration.thinking}
            }
        response = client.chat.completions.create(**request_kwargs)
        content = response.choices[0].message.content or ""
        return {
            "ok": bool(content.strip()),
            "duration_ms": round((perf_counter() - started) * 1000, 2),
            "model": response.model,
            "content_chars": len(content),
            "reasoning_chars": len(
                getattr(response.choices[0].message, "reasoning_content", "") or ""
            ),
        }
    except Exception as exc:  # noqa: BLE001 - diagnostic output is structured below
        return {
            "ok": False,
            "duration_ms": round((perf_counter() - started) * 1000, 2),
            "exception_type": f"{type(exc).__module__}.{type(exc).__name__}",
            "message": str(exc)[:500],
        }


def _checks_ok(checks: dict[str, object], chat_requested: bool) -> bool:
    for name in ("dns", "tcp", "https"):
        value = checks.get(name)
        if name == "dns":
            if not isinstance(value, dict) or not value.get("addresses"):
                return False
        elif not isinstance(value, dict) or not value.get("ok"):
            return False
    if chat_requested:
        value = checks.get("chat")
        return isinstance(value, dict) and bool(value.get("ok"))
    return True


def _safe_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.hostname:
        return "<invalid>"
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}{parsed.path.rstrip('/')}"


if __name__ == "__main__":
    raise SystemExit(main())
