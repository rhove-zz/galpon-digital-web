"""Command-line readiness gate for ACU deployments."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from typing import Any, Sequence


DEFAULT_URL = "http://127.0.0.1:8000/system/readiness"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the readiness gate and return a process exit code."""
    parser = argparse.ArgumentParser(
        description="Validate ACU /system/readiness before exposing a runtime."
    )
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument(
        "--api-key",
        default=os.getenv("ACU_READINESS_API_KEY", ""),
        help="Monitoring API key sent as X-ACU-API-Key.",
    )
    parser.add_argument("--retries", type=int, default=30)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on warning status instead of only failing on not_ready.",
    )
    args = parser.parse_args(argv)

    retries = max(args.retries, 1)
    for attempt in range(1, retries + 1):
        try:
            payload = _fetch_readiness(
                url=args.url,
                api_key=args.api_key,
                timeout=max(args.timeout, 0.1),
            )
            return _evaluate_readiness(payload=payload, strict=args.strict)
        except Exception as exc:
            if attempt == retries:
                print(f"readiness unavailable after {retries} attempt(s): {exc}")
                return 1
            time.sleep(max(args.delay, 0.0))
    return 1


def _fetch_readiness(url: str, api_key: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url)
    if api_key:
        request.add_header("X-ACU-API-Key", api_key)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw_body = response.read().decode("utf-8")
    payload = json.loads(raw_body)
    if not isinstance(payload, dict):
        raise ValueError("readiness response must be a JSON object")
    return payload


def _evaluate_readiness(payload: dict[str, Any], strict: bool) -> int:
    status = str(payload.get("status", "")).strip().lower()
    summary = payload.get("summary", {})
    print(f"readiness status={status} summary={summary}")

    if status == "ready":
        return 0
    if status == "warning" and not strict:
        return 0
    if status == "warning":
        print("readiness warning rejected because --strict is enabled")
        return 1
    if status == "not_ready":
        _print_failed_checks(payload)
        return 1

    print(f"unknown readiness status: {status}")
    return 1


def _print_failed_checks(payload: dict[str, Any]) -> None:
    checks = payload.get("checks", [])
    if not isinstance(checks, list):
        return
    for check in checks:
        if not isinstance(check, dict):
            continue
        if check.get("status") == "fail":
            name = check.get("name", "unknown")
            detail = check.get("detail", "")
            print(f"failed check: {name} - {detail}")


if __name__ == "__main__":
    sys.exit(main())
