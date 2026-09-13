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

このテストは `targets.*.workspace.host` にワークスペース URL が
直書きされていないかを検査する。

**注意**: `variables.*.default` にワークスペース URL 相当の文字列が入る
ことは問題ではない（`warehouse_id` や `agent_databricks_host` のように、
「このワークスペース向けの具体的なデフォルト値を持ちつつ `--var` で
上書きできる」という設計は、このプロジェクトが意図的に採用している
移植性の確保方法そのものである）。そのため、当初はファイル全体を
正規表現で走査していたが、`agent_databricks_host` の default 値
（意図的な設計）を誤検知したことがある。`targets.*.workspace.host` だけを
YAML としてパースして狙い撃ちする実装に直した。
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATABRICKS_YML = ROOT / "databricks.yml"


def test_targets_workspace_host_is_not_hardcoded():
    data = yaml.safe_load(DATABRICKS_YML.read_text(encoding="utf-8")) or {}

    violations = []
    for target_name, target in (data.get("targets") or {}).items():
        host = ((target or {}).get("workspace") or {}).get("host")
        if host:
            violations.append(f"targets.{target_name}.workspace.host = {host!r}")

    assert not violations, (
        "databricks.yml の targets.*.workspace.host にワークスペース URL が"
        " 直書きされています。ワークスペースごとに異なる値のため、"
        " `DATABRICKS_HOST` 環境変数か CLI プロファイル（`--profile`）で"
        " 指定する運用にしてください（README「B. ローカル PC の Databricks CLI"
        " からデプロイする」参照）:\n" + "\n".join(violations)
    )
