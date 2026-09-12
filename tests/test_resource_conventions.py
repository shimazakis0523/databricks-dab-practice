"""resources/*.yml の命名規則を検証するテスト（Spark 不要・高速）。

過去に踏んだ落とし穴の再発防止用:
`mode: development` は DAB 管理の `schemas` / `catalogs` リソースの
"物理名" を `dev_<user>_<name>` にリネームするが、他のリソースの
`catalog`/`schema`/`catalog_name`/`schema_name` に書いた文字列リテラルは
リネームされない。そのため、同じ UC スキーマを指しているつもりでも
片方だけリネームされてズレる、という事故が起きた
（landing volume が `nyctaxi` ではなく `dev_<user>_nyctaxi` に作られた）。

このテストは、`resources.schemas` / `resources.catalogs` の動的な名前
（`${resources.schemas...}` / `${resources.catalogs...}`）を
`catalog`/`schema`/`catalog_name`/`schema_name` の値として使っている
箇所がないかを検査する。このプロジェクトでは UC のスキーマ・カタログ参照は
必ず文字列リテラルで統一する、という規約を機械的に強制する。
"""

from pathlib import Path

import yaml

RESOURCES_DIR = Path(__file__).resolve().parents[1] / "resources"

# UC のカタログ/スキーマを指す可能性があるフィールド名
SCHEMA_OR_CATALOG_KEYS = {"catalog", "schema", "catalog_name", "schema_name"}

# このパターンを値に使うと、mode: development で物理名がリネームされる
# DAB 管理リソースを動的参照してしまい、他の文字列リテラル参照とズレる。
FORBIDDEN_REFERENCE_PREFIXES = ("${resources.schemas.", "${resources.catalogs.")


def _walk(node, path=()):
    """YAML をロードした dict/list を再帰的に (path, key, value) で辿る。"""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(value, path + (key,))
            if key in SCHEMA_OR_CATALOG_KEYS and isinstance(value, str):
                yield path + (key,), value
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from _walk(item, path + (index,))


def test_schema_and_catalog_references_are_literal_strings():
    """resources/*.yml の catalog/schema 系フィールドが、
    DAB 管理の schemas/catalogs リソースを動的参照していないことを確認する。

    mode: development はそれらリソースの物理名を dev_<user>_ 付きに
    リネームするため、動的参照と文字列リテラル参照が混在すると
    「同じ名前のつもりが別スキーマになる」事故につながる。
    """
    violations = []

    for yml_file in sorted(RESOURCES_DIR.glob("*.yml")):
        data = yaml.safe_load(yml_file.read_text())
        if not data:
            continue

        for path, value in _walk(data):
            if value.startswith(FORBIDDEN_REFERENCE_PREFIXES):
                violations.append(
                    f"{yml_file.name}: {'.'.join(map(str, path))} = {value!r}"
                )

    assert not violations, (
        "catalog/schema 系フィールドで resources.schemas / resources.catalogs を"
        " 動的参照している箇所があります。mode: development によるリネームで"
        " 他の文字列リテラル参照とズレるため、文字列リテラルに統一してください:\n"
        + "\n".join(violations)
    )
