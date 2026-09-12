# databricks-dab-practice への変更ガイド

## 構成変更・機能拡張をしたら README.md も必ず見直す

`resources/*.yml`・`pipelines/*.py`・`notebooks/*.py` の追加/削除/挙動変更を行った場合、
同じコミット（PR）で `README.md` の以下も更新すること:

- **「構成」セクションのファイルツリー** — 追加/削除したファイルを反映する
- **「このプロジェクトで検証している POC」の表** — 新しい検証観点が増えたら追記する
- **「全体構成図」の Mermaid フローチャート** — データの流れやトリガー関係が変わったら図も直す
- 該当するセクション本文（実行方法・注意点など）

これは `tests/test_readme_sync.py` で機械的にもチェックされる
（`resources/*.yml` / `pipelines/*.py` / `notebooks/*.py` のファイル名が
README.md 本文のどこかに出現しているかを検証するだけの簡易チェックだが、
更新し忘れの一次検知として機能する）。CI の `test` ジョブに含まれるため、
README を更新し忘れると CI が落ちる。

## その他の開発ルール

- Unity Catalog のカタログ/スキーマ参照（`catalog` / `schema` /
  `catalog_name` / `schema_name`）は文字列リテラルで統一する。理由と経緯は
  README の「開発時の注意点」を参照。`tests/test_resource_conventions.py`
  がこれも機械的にチェックする。
- パイプラインの変換ロジックは `dlt` に依存しない純粋関数として
  `pipelines/transforms.py` に切り出し、`tests/test_transforms.py` で
  pytest テストする（`nyctaxi_pipeline.py` 自体は Databricks 実行環境でしか
  import できないため）。
- コミット・push 前にローカルで `pytest tests/ -v` を実行して確認する。
