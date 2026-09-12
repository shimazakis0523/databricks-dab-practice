# Databricks notebook source
# MAGIC %md
# MAGIC # 閲覧者ロールへのテーブル単位の権限付与
# MAGIC
# MAGIC DAB の `grants`（`resources/nyctaxi_permissions.yml`）はスキーマ単位までしか
# MAGIC 宣言できないため、`nyctaxi-viewers` グループに `trips_daily_gold`
# MAGIC （日次集計の gold テーブル）だけを見せる、というテーブル単位の制御は
# MAGIC ここで明示的な SQL GRANT として発行する。
# MAGIC
# MAGIC - `trips_daily_gold` が存在してから（`nyctaxi_pipeline` を一度実行した後）に実行すること
# MAGIC - GRANT は何度実行しても安全（べき等）
# MAGIC - グループ `nyctaxi-viewers` は事前にワークスペースで作成しておくこと

# COMMAND ----------

# スキーマの中を一覧できるようにする（テーブルの中身自体は見せない）
spark.sql("GRANT USE SCHEMA ON SCHEMA workspace.nyctaxi TO `nyctaxi-viewers`")

# 閲覧を許可するのは日次集計の gold テーブルだけ
spark.sql("GRANT SELECT ON TABLE workspace.nyctaxi.trips_daily_gold TO `nyctaxi-viewers`")

print("nyctaxi-viewers に trips_daily_gold への SELECT 権限を付与しました。")
