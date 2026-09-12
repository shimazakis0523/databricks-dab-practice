"""Lakeview ダッシュボード（*.lvdash.json）の必須規約チェック（高速・レンダリング不要）。

過去に踏んだ落とし穴の再発防止用（3回目の教訓を含む）:

1. 各ウィジェットの `queries[].name` に任意の名前（例: `total_trips_query`）を
   付けていたが、Lakeview は単一クエリのウィジェットで `main_query` という
   固定名を要求する。違うと実ワークスペースで "Missing query main_query" に
   なる。
2. table ウィジェットの `encodings.columns` の `type` に無効な値
   （`"datetime"` の意味で `"date"` を使うなど）を指定すると、フィールド自体は
   存在していても実ワークスペースで "Invalid widget definition is imported"
   になる。**日付列の正しい値は `"datetime"`**（`"date"` という値は存在しない）。
   最初にこれを取り違えて `"date"` に「修正」してしまい、かえって規約違反を
   悪化させたことがある。GitHub 上の実際にエクスポートされた `.lvdash.json`
   （例: databricks/tmm リポジトリ）で確認できた値だけを許可リストにする。
3. table ウィジェットの各列は `type` 以外にも、実際にワークスペースが
   エクスポートする列オブジェクトが常に持っている一群のフィールド
   （`booleanValues` / `imageUrlTemplate` / `linkUrlTemplate` /
   `allowSearch` / `highlightLinks` / `useMonospaceFont` /
   `preserveWhitespace` / `displayName` など）を省略すると、`type` の値が
   正しくても "Invalid widget definition is imported" になることがあった。
   「`type` の値が許可リストに含まれるか」だけでなく「列オブジェクトが
   実エクスポート例と同じ必須フィールド一式を持っているか」も検証する。

このバンドルには `.lvdash.json` をライブのワークスペースに対して検証する
手段が無い（`databricks bundle validate` は JSON の構文チェックのみで、
Lakeview 固有のスキーマ規約までは検証しない）ため、実際にワークスペースへ
デプロイして初めて発覚する。このテストは、少なくとも過去に踏んだ規約違反の
再発を機械的に検知する（それでも「ワークスペースでの実表示確認」の代わりには
ならない。CLAUDE.md 参照）。
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARDS_DIR = ROOT / "dashboards"


def _load_dashboards():
    return sorted(DASHBOARDS_DIR.glob("*.lvdash.json"))


def _iter_table_columns(data):
    for page in data.get("pages", []):
        for item in page.get("layout", []):
            widget = item.get("widget", {})
            spec = widget.get("spec", {})
            if spec.get("widgetType") != "table":
                continue
            widget_name = widget.get("name", "<unnamed>")
            for column in spec.get("encodings", {}).get("columns", []):
                yield widget_name, column


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


# Lakeview の table ウィジェットが列型として受け付けることを、実際に
# ワークスペースがエクスポートした .lvdash.json（databricks/tmm リポジトリの
# サンプル）で確認できた値だけを保守的にリストする。日付列は "date" ではなく
# "datetime"（+ dateTimeFormat）が正しい値であり、この値の取り違えで
# 実際に "Invalid widget definition is imported" になったことがある。
# 他の型（boolean 等）を使う場合は、実際のワークスペースで確認してから
# ここに追加すること。
VALID_COLUMN_TYPES = {
    "string",
    "datetime",
    "integer",
    "decimal",
}

# table ウィジェットの列オブジェクトが実エクスポート例で常に持っている
# フィールド。これらを省略すると、type の値が正しくても
# "Invalid widget definition is imported" になったことがある。
REQUIRED_COLUMN_FIELDS = {
    "fieldName",
    "booleanValues",
    "imageUrlTemplate",
    "imageTitleTemplate",
    "imageWidth",
    "imageHeight",
    "linkUrlTemplate",
    "linkTextTemplate",
    "linkTitleTemplate",
    "linkOpenInNewTab",
    "type",
    "displayAs",
    "visible",
    "order",
    "title",
    "allowSearch",
    "alignContent",
    "allowHTML",
    "highlightLinks",
    "useMonospaceFont",
    "preserveWhitespace",
    "displayName",
}


def test_table_widget_columns_declare_a_valid_type():
    violations = []
    for path in _load_dashboards():
        data = json.loads(path.read_text(encoding="utf-8"))
        for widget_name, column in _iter_table_columns(data):
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


def test_table_widget_columns_have_all_required_fields():
    violations = []
    for path in _load_dashboards():
        data = json.loads(path.read_text(encoding="utf-8"))
        for widget_name, column in _iter_table_columns(data):
            missing = REQUIRED_COLUMN_FIELDS - column.keys()
            if missing:
                violations.append(
                    f"{path.name}: widget={widget_name}"
                    f" column={column.get('fieldName')!r} missing={sorted(missing)}"
                )

    assert not violations, (
        "table ウィジェットの encodings.columns に、実エクスポート例が常に持つ"
        " フィールドが不足しています。type の値が正しくても、これらが無いと"
        " 実ワークスペースで 'Invalid widget definition is imported' に"
        " なることがあります:\n"
        + "\n".join(violations)
    )
