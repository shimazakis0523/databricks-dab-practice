#!/usr/bin/env python3
"""resources/groups.json に定義されていないグループを検知し、削除する。

IaC（resources/groups.json）に存在しないグループは
「あってはならない存在」とみなし、既定で削除する。

例外は Databricks のシステム予約グループ:
- `admins`: 公式ドキュメントで「削除不可の予約グループ」と明記されている
- `users`: ワークスペースの全ユーザーが自動的に所属する既定グループ。
  削除可否は公式に明記されていないが、削除するとワークスペース全体の
  アクセス基盤に影響しかねないため、常に保護対象として扱う

これら以外の未定義グループはすべて削除候補。`--dry-run` を付けると
検知のみ（削除しない）で終了する。

環境変数 DATABRICKS_HOST / DATABRICKS_TOKEN が必要。
"""

from __future__ import annotations

import json
import os
import sys

from scim_client import GROUPS_PATH, call_api, list_all

GROUPS_FILE = os.path.join(os.path.dirname(__file__), "..", "resources", "groups.json")

# 技術的に削除できても、削除してはならないシステム予約グループ。
PROTECTED_SYSTEM_GROUPS = {"admins", "users"}


def load_declared_group_names() -> set[str]:
    with open(GROUPS_FILE, encoding="utf-8") as f:
        groups = json.load(f)
    groups.pop("_comment", None)
    return set(groups.keys())


def delete_group(host: str, token: str, group_id: str) -> None:
    call_api(host, token, "DELETE", f"{GROUPS_PATH}/{group_id}")


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    host = os.environ["DATABRICKS_HOST"]
    token = os.environ["DATABRICKS_TOKEN"]

    declared = load_declared_group_names()
    all_groups = list_all(host, token, GROUPS_PATH)

    undeclared = [
        g
        for g in all_groups
        if g.get("displayName") not in declared
        and g.get("displayName") not in PROTECTED_SYSTEM_GROUPS
    ]

    if not undeclared:
        print("[audit_undeclared_groups] IaC 未定義のグループはありません。")
        return 0

    print(f"[audit_undeclared_groups] IaC 未定義のグループを {len(undeclared)} 件検出しました:")
    for group in undeclared:
        print(f"  - {group.get('displayName')} (id={group.get('id')})")

    if dry_run:
        print("[audit_undeclared_groups] --dry-run のため削除は行いません。")
        return 0

    for group in undeclared:
        name = group.get("displayName")
        print(f"[audit_undeclared_groups] '{name}' を削除します。")
        delete_group(host, token, group["id"])
        print(f"[audit_undeclared_groups] '{name}' を削除しました。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
