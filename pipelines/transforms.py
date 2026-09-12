"""nyctaxi_pipeline.py が使う変換ロジック（純粋関数）。

DLT デコレータに依存しないプレーンな PySpark 関数として切り出すことで、
Databricks 上のパイプライン実行なしに pytest でユニットテストできるようにしています。
Lakeflow Declarative Pipelines はパイプラインのルートディレクトリを自動的に
sys.path に追加するため、nyctaxi_pipeline.py から `from transforms import ...`
として通常の Python import で参照できます。
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

# Silver 層で不正なレコードを除外するための品質ルール。
# nyctaxi_pipeline.py の @dlt.expect_all_or_drop にもそのまま渡すので、
# ロジックの重複を避けるためここで一元管理する。
QUALITY_EXPECTATIONS = {
    "valid_fare": "fare_amount > 0",
    "valid_distance": "trip_distance > 0",
    "valid_period": "tpep_dropoff_datetime > tpep_pickup_datetime",
}


def add_trip_metrics(df: DataFrame) -> DataFrame:
    """乗車日・乗車時間(分)・距離あたり運賃の列を付与する。"""
    return (
        df.withColumn("pickup_date", F.to_date("tpep_pickup_datetime"))
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


def aggregate_daily(df: DataFrame) -> DataFrame:
    """乗車日 × 乗車 ZIP ごとに件数・平均運賃・平均距離・平均乗車時間を集計する。"""
    return df.groupBy("pickup_date", "pickup_zip").agg(
        F.count("*").alias("trip_count"),
        F.round(F.avg("fare_amount"), 2).alias("avg_fare"),
        F.round(F.avg("trip_distance"), 2).alias("avg_distance"),
        F.round(F.avg("trip_minutes"), 1).alias("avg_trip_minutes"),
    )
