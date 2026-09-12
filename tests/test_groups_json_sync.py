"""resources/groups.json の中身（entitlements の値）が README.md に
正しく転記されているかを検証する（Spark 不要・高速）。

`tests/test_readme_sync.py` は「ファイルの存在」しか見ておらず、
「設定ファイルの中身の値が人間向けドキュメントとして正しく転記されているか」
までは検証していなかった。その結果、`resources/groups.json` に
`workspace-consume` を追加した際、README の権限テーブルへの反映漏れが
レビュー指摘があるまで検知できなかった（CLAUDE.md の「メタルール」参照）。

このテストはその穴を埋める: groups.json の各グループの entitlements 値が
1つ残らず README.md 本文に出現しているかを確認する。値そのものの
出現チェックであり、ファイル名チェックより一段深い（が、依然として
「表として正しく整形されているか」までは保証しない簡易チェック）。
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS_JSON = ROOT / "resources" / "groups.json"
README_TEXT = (ROOT / "README.md").read_text(encoding="utf-8")


def test_every_group_entitlement_value_is_documented_in_readme():
    groups = json.loads(GROUPS_JSON.read_text(encoding="utf-8"))
    groups.pop("_comment", None)

    missing = []
    for group_name, config in groups.items():
        # グループ名自体も README に出ているべき（表の行が無い、を検知する）
        if group_name not in README_TEXT:
            missing.append(f"{group_name} (グループ名自体が README に無い)")

        for entitlement in config.get("entitlements", []):
            if entitlement not in README_TEXT:
                missing.append(f"{group_name}: entitlement '{entitlement}'")

    assert not missing, (
        "resources/groups.json の内容が README.md に転記されていません。"
        " 「組織/権限管理」セクションの entitlements テーブルを"
        " resources/groups.json の実際の値と一致させてください"
        " （CLAUDE.md のメタルール参照）:\n" + "\n".join(missing)
    )
