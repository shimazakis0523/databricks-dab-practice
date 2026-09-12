#!/usr/bin/env python3
"""グループ経由ではない、ユーザーへの直接 entitlements 付与を検知する。

ガバナンスをグループ（resources/groups.json）に一本化する方針のもとでは、
ユーザー個人に直接 entitlements が付与されている状態は「本来グループ経由で
継承されるべきものが、個人設定として別系統に漏れている」ドリフトとみなせる。

このスクリプトは検知のみを行う（自動修正はしない）:
- ワークスペースの全ユーザーと全グループを取得
- 各ユーザーについて、本人に直接付与された entitlements と、
  所属する各グループの entitlements（の和集合）を比較する
- 直接付与分がグループ経由の分でカバーされていなければ報告する

ノート: 実際にワークスペースを管理しているアカウント（作成者/オーナー）は、
`admins` グループなどを通じて、あるいは直接、`nyctaxi-*` グループの管理外の
entitlements を持っているのが正常なケースが多い。誤検知で CI を止めないよう、
このスクリプトは常に exit code 0 で終了し、レポートの出力のみを行う。

環境変数 DATABRICKS_HOST / DATABRICKS_TOKEN が必要。
"""

from __future__ import annotations

import os
import sys

from scim_client import GROUPS_PATH, USERS_PATH, list_all


def main() -> int:
    host = os.environ["DATABRICKS_HOST"]
    token = os.environ["DATABRICKS_TOKEN"]

    groups = list_all(host, token, GROUPS_PATH)
    group_entitlements_by_id = {
        g["id"]: {e["value"] for e in g.get("entitlements", [])} for g in groups
    }
    group_name_by_id = {g["id"]: g.get("displayName", g["id"]) for g in groups}

    users = list_all(host, token, USERS_PATH)

    findings = []
    for user in users:
        direct = {e["value"] for e in user.get("entitlements", [])}
        if not direct:
            continue

        member_group_ids = [m.get("value") for m in user.get("groups", [])]
        inherited: set[str] = set()
        for gid in member_group_ids:
            inherited |= group_entitlements_by_id.get(gid, set())

        extra = direct - inherited
        if extra:
            user_name = user.get("userName", user.get("id"))
            group_names = [group_name_by_id.get(gid, gid) for gid in member_group_ids]
            findings.append((user_name, sorted(extra), group_names))

    if not findings:
        print("[audit_user_entitlements] グループ経由ではない直接 entitlements は見つかりませんでした。")
        return 0

    print(
        f"[audit_user_entitlements] グループ経由ではない直接 entitlements を"
        f" {len(findings)} 名のユーザーで検出しました（自動修正はしていません）:"
    )
    for user_name, extra, group_names in findings:
        print(f"  - {user_name}: 直接付与 {extra} / 所属グループ {group_names}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
