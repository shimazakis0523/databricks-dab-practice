# Databricks notebook source
# MAGIC %md
# MAGIC # NYC Taxi メダリオンパイプライン
# MAGIC Lakeflow Declarative Pipelines (旧 Delta Live Tables) で
# MAGIC bronze → silver → gold の3層を宣言的に定義します。
# MAGIC
# MAGIC ソースデータ: `samples.nyctaxi.trips`（Databricks に最初から用意されているサンプル）

# COMMAND ----------

import dlt
from pyspark.sql import functions as F

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
@dlt.expect_all_or_drop(
    {
        "valid_fare": "fare_amount > 0",
        "valid_distance": "trip_distance > 0",
        "valid_period": "tpep_dropoff_datetime > tpep_pickup_datetime",
    }
)
def trips_silver():
    return (
        dlt.read("trips_bronze")
        .withColumn("pickup_date", F.to_date("tpep_pickup_datetime"))
        .withColumn(
            "trip_minutes",
            (
                F.unix_timestamp("tpep_dropoff_datetime")
                - F.unix_timestamp("tpep_pickup_datetime")
            )
            / 60,
        )
        .withColumn("fare_per_mile", F.col("fare_amount") / F.col("trip_distance"))
    )


# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold: 日次 × 乗車エリアの集計

# COMMAND ----------


@dlt.table(
    name="trips_daily_gold",
    comment="乗車日 × 乗車 ZIP ごとの件数・平均運賃・平均距離",
)
def trips_daily_gold():
    return (
        dlt.read("trips_silver")
        .groupBy("pickup_date", "pickup_zip")
        .agg(
            F.count("*").alias("trip_count"),
            F.round(F.avg("fare_amount"), 2).alias("avg_fare"),
            F.round(F.avg("trip_distance"), 2).alias("avg_distance"),
            F.round(F.avg("trip_minutes"), 1).alias("avg_trip_minutes"),
        )
    )
