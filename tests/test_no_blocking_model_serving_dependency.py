"""resources/*.yml が「手動 Job でしか作られないリソース」に依存していないかの
チェック（Spark 不要・高速）。

過去に踏んだ落とし穴の再発防止用:
`resources/gold_qa_agent_serving.yml`（model_serving_endpoints）が、
Unity Catalog に登録済みのモデル（`gold_qa_agent_registration_job` という
手動実行の Job でしか作られない）を entity_name で参照していた。
`resources/*.yml` は CI から毎回自動デプロイされるため、モデル登録前は
`databricks bundle deploy` が "Registered model ... does not exist" で
失敗し、しかもこの1リソースの失敗が bundle 全体のデプロイを止めて
しまった（他の無関係なリソースのデプロイまで巻き込む事故になった）。

このプロジェクトには「手動 Job の実行結果に依存する resources.*」を
自動デプロイと手動デプロイに分離する仕組みが無いため、当面は
`resources/*.yml` に `model_serving_endpoints` を置かない、という運用で
このクラスの事故を防ぐ（`templates/*.yml` に置き、README の手順に従って
モデル登録後に手動で `resources/` へコピーする）。この制約を
機械的に強制するのがこのテスト。
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RESOURCES_DIR = ROOT / "resources"

# resources/*.yml（CI が毎回自動デプロイする対象）に置いてはならないリソース種別。
# 「別の手動 Job でしか作られない外部エンティティを参照し、それが存在しないと
# デプロイ自体が失敗する」タイプのリソースはここに追加する。
BLOCKING_RESOURCE_TYPES = {"model_serving_endpoints"}


def test_resources_dir_has_no_blocking_manual_dependency_resources():
    violations = []
    for yml_file in sorted(RESOURCES_DIR.glob("*.yml")):
        data = yaml.safe_load(yml_file.read_text())
        if not data:
            continue
        resource_types = set(data.get("resources", {}).keys())
        found = resource_types & BLOCKING_RESOURCE_TYPES
        if found:
            violations.append(f"{yml_file.name}: {sorted(found)}")

    assert not violations, (
        "resources/*.yml に、手動 Job でしか作られない外部リソースへの参照を"
        " 含むリソース種別があります。これは CI の自動デプロイ全体を"
        " ブロックする事故につながります（CLAUDE.md 参照）。"
        " templates/*.yml に置き、手動 Job 実行後に手動でコピーする運用に"
        " してください:\n" + "\n".join(violations)
    )
