"""ワークスペースレベルの SCIM API を叩くための共通ヘルパー。

ensure_groups.py / audit_undeclared_groups.py / audit_user_entitlements.py
から共通で使う。Free Edition にはアカウントコンソール/SCIM 同期がないため、
`/api/2.0/preview/scim/v2/...` のワークスペーススコープのエンドポイントを
直接呼び出す。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

GROUPS_PATH = "/api/2.0/preview/scim/v2/Groups"
USERS_PATH = "/api/2.0/preview/scim/v2/Users"


def call_api(host: str, token: str, method: str, path: str, body: dict | None = None) -> dict:
    url = f"{host.rstrip('/')}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/scim+json")
    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed: HTTP {error.code}: {detail}") from error


def list_all(host: str, token: str, base_path: str, page_size: int = 100) -> list[dict]:
    """SCIM の startIndex/count ページングを辿って全件取得する。"""
    resources: list[dict] = []
    start_index = 1
    while True:
        query = urllib.parse.urlencode({"startIndex": start_index, "count": page_size})
        result = call_api(host, token, "GET", f"{base_path}?{query}")
        page = result.get("Resources", [])
        resources.extend(page)
        total = result.get("totalResults", len(resources))
        if start_index + len(page) - 1 >= total or not page:
            break
        start_index += page_size
    return resources


def find_group_by_name(host: str, token: str, name: str) -> dict | None:
    query = urllib.parse.quote(f'displayName eq "{name}"')
    result = call_api(host, token, "GET", f"{GROUPS_PATH}?filter={query}")
    resources = result.get("Resources", [])
    return resources[0] if resources else None
