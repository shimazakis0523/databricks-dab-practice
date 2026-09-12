"""Lakeview ダッシュボード（*.lvdash.json）の必須規約チェック（高速・レンダリング不要）。

過去に踏んだ落とし穴の再発防止用:
`nyctaxi_gold_dashboard.lvdash.json` を手書きした際、各ウィジェットの
`queries[].name` に任意の名前（例: `total_trips_query`）を付けていたが、
Lakeview は単一クエリのウィジェットで `main_query` という固定名を要求する。
この名前が違うと実際のワークスペースでは "Missing query main_query" として
描画に失敗する。また table ウィジェットの `encodings.columns` に `type` が
無いと "Invalid widget definition is imported" として描画に失敗する。

このバンドルには `.lvdash.json` をライブのワークスペースに対して検証する
手段が無い（`databricks bundle validate` は JSON の構文チェックのみで、
Lakeview 固有のスキーマ規約までは検証しない）ため、実際にワークスペースへ
デプロイして初めて発覚した。このテストは、少なくとも過去に踏んだ規約違反の
再発を機械的に検知する。
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARDS_DIR = ROOT / "dashboards"


def _load_dashboards():
    return sorted(DASHBOARDS_DIR.glob("*.lvdash.json"))


def test_widget_queries_are_named_main_query():
    violations = []
    for path in _load_dashboards():
        data = json.loads(path.read_text(encoding="utf-8"))
        for page in data.get("pages", []):
            for item in page.get("layout", []):
                widget = item.get("widget", {})
                widget_name = widget.get("name", "<unnamed>")
                for query in widget.get("queries", []):
                    if query.get("name") != "main_query":
                        violations.append(
                            f"{path.name}: widget={widget_name} query.name={query.get('name')!r}"
                        )

    assert not violations, (
        "Lakeview ウィジェットの queries[].name は 'main_query' である必要があります"
        "（実ワークスペースで 'Missing query main_query' エラーになります）:\n"
        + "\n".join(violations)
    )


def test_table_widget_columns_declare_a_type():
    violations = []
    for path in _load_dashboards():
        data = json.loads(path.read_text(encoding="utf-8"))
        for page in data.get("pages", []):
            for item in page.get("layout", []):
                widget = item.get("widget", {})
                spec = widget.get("spec", {})
                if spec.get("widgetType") != "table":
                    continue
                widget_name = widget.get("name", "<unnamed>")
                for column in spec.get("encodings", {}).get("columns", []):
                    if "type" not in column:
                        violations.append(
                            f"{path.name}: widget={widget_name} column={column.get('fieldName')!r}"
                        )

    assert not violations, (
        "table ウィジェットの encodings.columns には 'type' が必須です"
        "（無いと実ワークスペースで 'Invalid widget definition is imported' に"
        "なります）:\n"
        + "\n".join(violations)
    )
