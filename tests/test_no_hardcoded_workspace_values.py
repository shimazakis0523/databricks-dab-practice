"""環境依存値のハードコード防止テスト（Spark 不要・高速）。

過去に踏んだ落とし穴の再発防止用:
`databricks.yml` の `targets.dev.workspace.host` にワークスペース URL を
文字列直書きしていたため、この bundle を別のワークスペース（本番導入
プロジェクトなど）に持ち込むと、host を書き換えない限り誤ったワークスペースに
デプロイされる/認証エラーになるという問題があった。

`warehouse_id` のような値は `databricks.yml` の `variables` に切り出す
ルールが既にあったにもかかわらず、`workspace.host` には同じルールを
適用し忘れていた（ルールが「一般論」として書かれていて、具体的にどの
フィールドが対象かを機械的にチェックしていなかったのが根本原因）。

このテストは `databricks.yml` に `*.cloud.databricks.com` 形式の
ワークスペース URL が直書きされていないかを検査する。
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABRICKS_YML = ROOT / "databricks.yml"

# https://<workspace-id>.cloud.databricks.com 形式のワークスペース URL パターン。
WORKSPACE_URL_PATTERN = re.compile(r"https://[a-zA-Z0-9-]+\.cloud\.databricks\.com")


def test_databricks_yml_has_no_hardcoded_workspace_host():
    text = DATABRICKS_YML.read_text(encoding="utf-8")
    matches = WORKSPACE_URL_PATTERN.findall(text)

    assert not matches, (
        "databricks.yml にワークスペース URL が直書きされています。"
        " ワークスペースごとに異なる値のため、`workspace.host` を直書きせず、"
        " `DATABRICKS_HOST` 環境変数か CLI プロファイル（`--profile`）で"
        " 指定する運用にしてください（README「B. ローカル PC の Databricks CLI"
        " からデプロイする」参照）:\n"
        + "\n".join(matches)
    )
