#!/usr/bin/env python3
"""Dependency-free Awaazify production smoke test."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def request(url: str, method: str = "GET", headers: dict[str, str] | None = None):
    req = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status, {key.lower(): value for key, value in response.headers.items()}, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, {key.lower(): value for key, value in exc.headers.items()}, exc.read().decode("utf-8", "replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend", default="https://awaazify.pages.dev")
    parser.add_argument("--api", default="https://nabeeljarwar022--awaazify-api-web.us-east.modal.run")
    args = parser.parse_args()
    frontend, api = args.frontend.rstrip("/"), args.api.rstrip("/")
    results: list[tuple[str, bool, str]] = []

    status, headers, body = request(frontend)
    results.append(("Frontend reachable", status == 200 and "Awaazify" in body, f"HTTP {status}"))

    status, headers, body = request(f"{api}/api/v1/health")
    try:
        health = json.loads(body)
    except json.JSONDecodeError:
        health = {}
    results.append(("API health", status == 200 and health.get("status") == "ok", f"HTTP {status}"))
    results.append(("Security nosniff", headers.get("x-content-type-options", "").lower() == "nosniff", headers.get("x-content-type-options", "missing")))
    results.append(("Clickjacking protection", headers.get("x-frame-options", "").upper() == "DENY", headers.get("x-frame-options", "missing")))
    results.append(("Request ID", bool(headers.get("x-request-id")), "present" if headers.get("x-request-id") else "missing"))

    status, _, body = request(f"{api}/api/v1/health/ready")
    results.append(("API readiness", status == 200, f"HTTP {status}: {body[:120]}"))

    status, _, _ = request(f"{api}/api/v1/me")
    results.append(("Protected route rejects anonymous", status == 401, f"HTTP {status}"))

    status, cors_headers, _ = request(
        f"{api}/api/v1/me", "OPTIONS",
        {"Origin": frontend, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"},
    )
    allowed = cors_headers.get("access-control-allow-origin") == frontend
    results.append(("Production CORS", status in {200, 204} and allowed, f"HTTP {status}; origin={cors_headers.get('access-control-allow-origin','missing')}"))

    print("\nAwaazify production smoke test\n")
    for name, ok, detail in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    failed = sum(not ok for _, ok, _ in results)
    print(f"\n{len(results)-failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

