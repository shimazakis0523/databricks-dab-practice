# Databricks notebook source
# MAGIC %md
# MAGIC # ロールごとの権限付与
# MAGIC
# MAGIC 組織の3つのロールを、事前にワークスペースで作成したグループに対応させ、
# MAGIC `nyctaxi` スキーマ / `trips_daily_gold` テーブルへの権限を発行する。
# MAGIC
# MAGIC | ロール | グループ名 | 権限 |
# MAGIC | --- | --- | --- |
# MAGIC | データエンジニア | `nyctaxi-data-engineers` | `nyctaxi` スキーマへの `ALL_PRIVILEGES` |
# MAGIC | アナリスト | `nyctaxi-analysts` | `nyctaxi` スキーマへの `USE_SCHEMA` + `SELECT`（bronze/silver/gold すべて） |
# MAGIC | 閲覧者 | `nyctaxi-viewers` | `trips_daily_gold` テーブルのみ `SELECT` |
# MAGIC
# MAGIC ## なぜ DAB の `grants` ではなく SQL で発行しているか
# MAGIC
# MAGIC `nyctaxi` スキーマは `nyctaxi_pipeline` の初回実行時に自動作成されており、
# MAGIC DAB（バンドル）の管理下にない。この状態で `resources.schemas` として
# MAGIC 同名のスキーマを宣言すると `SCHEMA_ALREADY_EXISTS` で `bundle deploy` が失敗する
# MAGIC （`databricks bundle deployment bind` で既存リソースを取り込む手もあるが、
# MAGIC 学習用途でそこまでは踏み込まず、明示的な SQL GRANT で運用している）。
# MAGIC
# MAGIC また DAB の `grants` はスキーマ単位までしか宣言できず、
# MAGIC 「閲覧者には `trips_daily_gold` だけ見せる」というテーブル単位の制御は
# MAGIC そもそも DAB では表現できない。そのため、3ロールすべてをここに統一している。
# MAGIC
# MAGIC ## 実行タイミング
# MAGIC
# MAGIC - `trips_daily_gold` が存在してから（`nyctaxi_pipeline` を一度実行した後）に実行すること
# MAGIC - 何度実行しても安全（べき等）
# MAGIC - グループを作り直したときは再実行すること
# MAGIC - グループ（`nyctaxi-data-engineers` / `nyctaxi-analysts` / `nyctaxi-viewers`）は
# MAGIC   事前にワークスペースの Settings > Identity and access > Groups で作成しておくこと

# COMMAND ----------

# データエンジニア: nyctaxi スキーマへのフルアクセス
spark.sql("GRANT ALL PRIVILEGES ON SCHEMA workspace.nyctaxi TO `nyctaxi-data-engineers`")

# アナリスト: nyctaxi スキーマの参照のみ（bronze/silver/gold すべて）
spark.sql("GRANT USE SCHEMA ON SCHEMA workspace.nyctaxi TO `nyctaxi-analysts`")
spark.sql("GRANT SELECT ON SCHEMA workspace.nyctaxi TO `nyctaxi-analysts`")

# 閲覧者: trips_daily_gold（集計済みデータ）のみ参照可能
spark.sql("GRANT USE SCHEMA ON SCHEMA workspace.nyctaxi TO `nyctaxi-viewers`")
spark.sql("GRANT SELECT ON TABLE workspace.nyctaxi.trips_daily_gold TO `nyctaxi-viewers`")

print("nyctaxi-data-engineers / nyctaxi-analysts / nyctaxi-viewers への権限付与が完了しました。")
