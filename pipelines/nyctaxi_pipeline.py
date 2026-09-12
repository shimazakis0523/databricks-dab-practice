# Databricks notebook source
# MAGIC %md
# MAGIC # NYC Taxi メダリオンパイプライン
# MAGIC Lakeflow Declarative Pipelines (旧 Delta Live Tables) で
# MAGIC bronze → silver → gold の3層を宣言的に定義します。
# MAGIC
# MAGIC ソースデータ: Unity Catalog Volume `/Volumes/workspace/nyctaxi/landing` に置かれた
# MAGIC CSV ファイル（`notebooks/seed_nyctaxi_csv.py` が `samples.nyctaxi.trips` から生成）を
# MAGIC Auto Loader で増分取り込みします。実際の現場でよくある
# MAGIC 「ストレージに CSV が置かれる → 増分で読み込む」という構成を再現したものです。
# MAGIC
# MAGIC 変換ロジックは `transforms.py` に切り出してあり、pytest でユニットテスト済みです。

# COMMAND ----------

import dlt

from transforms import (
    QUALITY_EXPECTATIONS,
    add_trip_metrics,
    aggregate_daily,
    cast_raw_trip_columns,
)

LANDING_PATH = "/Volumes/workspace/nyctaxi/landing"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bronze: CSV を Auto Loader で増分取り込み
# MAGIC CSV は既定ではすべて文字列として取り込まれる（実務のランディングゾーンと同じ状態）。
# MAGIC 型変換は行わず、そのまま Silver に渡す。

# COMMAND ----------


@dlt.table(
    name="trips_bronze",
    comment="Auto Loader で landing volume の CSV を増分取り込みした生データ（すべて文字列）",
)
def trips_bronze():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("header", "true")
        .load(LANDING_PATH)
    )


# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver: 型変換・品質チェック・クレンジング
# MAGIC CSV 由来の文字列カラムを `cast_raw_trip_columns` で型変換したうえで、
# MAGIC `@dlt.expect_all_or_drop` により条件を満たさない行を除外する。

# COMMAND ----------


@dlt.table(
    name="trips_silver",
    comment="型変換・不正レコード除外を行い、乗車時間と距離あたり運賃を付与した明細",
)
@dlt.expect_all_or_drop(QUALITY_EXPECTATIONS)
def trips_silver():
    typed = cast_raw_trip_columns(dlt.read("trips_bronze"))
    return add_trip_metrics(typed)


# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold: 日次 × 乗車エリアの集計

# COMMAND ----------


@dlt.table(
    name="trips_daily_gold",
    comment="乗車日 × 乗車 ZIP ごとの件数・平均運賃・平均距離",
)
def trips_daily_gold():
    return aggregate_daily(dlt.read("trips_silver"))
