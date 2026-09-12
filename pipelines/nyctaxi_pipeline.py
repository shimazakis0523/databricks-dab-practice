# Databricks notebook source
# MAGIC %md
# MAGIC # NYC Taxi メダリオンパイプライン
# MAGIC Lakeflow Declarative Pipelines (旧 Delta Live Tables) で
# MAGIC bronze → silver → gold の3層を宣言的に定義します。
# MAGIC
# MAGIC ソースデータ: `samples.nyctaxi.trips`（Databricks に最初から用意されているサンプル）
# MAGIC
# MAGIC 変換ロジックは `transforms.py` に切り出してあり、pytest でユニットテスト済みです。

# COMMAND ----------

import dlt

from transforms import QUALITY_EXPECTATIONS, add_trip_metrics, aggregate_daily

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bronze: 生データをそのまま取り込む

# COMMAND ----------


@dlt.table(
    name="trips_bronze",
    comment="samples.nyctaxi.trips をそのまま取り込んだ生データ",
)
def trips_bronze():
    return spark.read.table("samples.nyctaxi.trips")


# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver: 品質チェックとクレンジング
# MAGIC `@dlt.expect_all_or_drop` で条件を満たさない行を除外します。

# COMMAND ----------


@dlt.table(
    name="trips_silver",
    comment="不正なレコードを除外し、乗車時間と距離あたり運賃を付与した明細",
)
@dlt.expect_all_or_drop(QUALITY_EXPECTATIONS)
def trips_silver():
    return add_trip_metrics(dlt.read("trips_bronze"))


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
