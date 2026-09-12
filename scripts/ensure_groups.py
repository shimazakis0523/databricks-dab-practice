#!/usr/bin/env python3
"""resources/groups.json のグループを作成し、entitlements を同期する。

Databricks Free Edition はアカウントコンソール/SCIM 同期/SSO が使えないため
`databricks account groups ...` は使えない。代わりに、ワークスペース単位の
SCIM Groups API (/api/2.0/preview/scim/v2/Groups) を直接呼び出す。

グループが存在しなければ作成し、存在すれば entitlements を
resources/groups.json の内容に同期する（べき等）。これにより、
「ワークスペースの Add user 画面でユーザーごとに entitlements を
トグルする」という別系統のガバナンスを使わず、グループ経由の
entitlements 継承だけでワークスペース機能へのアクセス権も統一管理する。

環境変数 DATABRICKS_HOST / DATABRICKS_TOKEN が必要
（CI の deploy ジョブと同じ認証情報を利用する）。
"""

from __future__ import annotations

import json
import os
import sys

from scim_client import GROUPS_PATH, call_api, find_group_by_name

GROUPS_FILE = os.path.join(os.path.dirname(__file__), "..", "resources", "groups.json")


def create_group(host: str, token: str, name: str, entitlement_values: list[str]) -> None:
    call_api(
        host,
        token,
        "POST",
        GROUPS_PATH,
        {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "displayName": name,
            "entitlements": [{"value": v} for v in entitlement_values],
        },
    )


def sync_entitlements(host: str, token: str, group_id: str, entitlement_values: list[str]) -> None:
    call_api(
        host,
        token,
        "PATCH",
        f"{GROUPS_PATH}/{group_id}",
        {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {
                    "op": "replace",
                    "path": "entitlements",
                    "value": [{"value": v} for v in entitlement_values],
                }
            ],
        },
    )


def main() -> int:
    host = os.environ["DATABRICKS_HOST"]
    token = os.environ["DATABRICKS_TOKEN"]

    with open(GROUPS_FILE, encoding="utf-8") as f:
        groups = json.load(f)
    groups.pop("_comment", None)

    for name, config in groups.items():
        desired = sorted(config.get("entitlements", []))
        existing = find_group_by_name(host, token, name)

        if existing is None:
            print(f"[ensure_groups] '{name}' を作成します（entitlements: {desired}）。")
            create_group(host, token, name, desired)
            print(f"[ensure_groups] '{name}' を作成しました。")
            continue

        current = sorted(e["value"] for e in existing.get("entitlements", []))
        if current == desired:
            print(f"[ensure_groups] '{name}' は既に存在し、entitlements も一致しています。スキップします。")
            continue

        print(f"[ensure_groups] '{name}' の entitlements を同期します（{current} -> {desired}）。")
        sync_entitlements(host, token, existing["id"], desired)
        print(f"[ensure_groups] '{name}' の entitlements を更新しました。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
