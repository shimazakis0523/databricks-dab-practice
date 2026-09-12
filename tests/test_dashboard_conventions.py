"""Lakeview ダッシュボード（*.lvdash.json）の必須規約チェック（高速・レンダリング不要）。

過去に踏んだ落とし穴の再発防止用:
`nyctaxi_gold_dashboard.lvdash.json` を手書きした際、各ウィジェットの
`queries[].name` に任意の名前（例: `total_trips_query`）を付けていたが、
Lakeview は単一クエリのウィジェットで `main_query` という固定名を要求する。
この名前が違うと実際のワークスペースでは "Missing query main_query" として
描画に失敗する。また table ウィジェットの `encodings.columns` は `type` が必須なだけでなく、
許容される値も決まっている（例: 日付列は `"datetime"` ではなく `"date"` を
使い、`dateTimeFormat` を併記する）。無効な値を指定すると "Invalid widget
definition is imported" として、ウィジェット全体が描画に失敗する
（`type` が存在してもエラーになるため、存在チェックだけでは不十分だった）。

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


# Lakeview の table ウィジェットが列型として受け付けることを実例で確認できた値
# （このバンドルで実際に使っているものだけを保守的にリストする。他の型
# （boolean 等）を使う場合は、実際のワークスペースで確認してからここに追加すること）。
# "datetime" はここに存在しない ("date" + dateTimeFormat が正しい) —
# 実際にこの値を使って "Invalid widget definition is imported" になった。
VALID_COLUMN_TYPES = {
    "string",
    "date",
    "integer",
    "decimal",
}


def test_table_widget_columns_declare_a_valid_type():
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
                    column_type = column.get("type")
                    if column_type not in VALID_COLUMN_TYPES:
                        violations.append(
                            f"{path.name}: widget={widget_name}"
                            f" column={column.get('fieldName')!r} type={column_type!r}"
                        )

    assert not violations, (
        "table ウィジェットの encodings.columns.type が未指定か、Lakeview が"
        f" 受け付けない値になっています（許容値: {sorted(VALID_COLUMN_TYPES)}）。"
        " 無効だとウィジェット全体が実ワークスペースで"
        " 'Invalid widget definition is imported' になります:\n"
        + "\n".join(violations)
    )
