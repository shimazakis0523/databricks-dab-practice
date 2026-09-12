"""pipelines/transforms.py のユニットテスト。

nyctaxi_pipeline.py 自体は Databricks の Lakeflow Declarative Pipelines
実行環境でのみ動く（`dlt` モジュールがそこにしか存在しない）ため、
テスト可能な変換ロジックは pipelines/transforms.py に切り出してある。
ここではその純粋関数だけを、ローカルの PySpark で検証する。
"""

import sys
from datetime import datetime
from pathlib import Path

import pyspark.sql.functions as F
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipelines"))

from transforms import (  # noqa: E402
    QUALITY_EXPECTATIONS,
    add_trip_metrics,
    aggregate_daily,
    cast_raw_trip_columns,
)

RAW_COLUMNS = [
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "fare_amount",
    "trip_distance",
    "pickup_zip",
]


def make_trip(pickup, dropoff, fare_amount, trip_distance, pickup_zip=10001):
    return (
        datetime.fromisoformat(pickup),
        datetime.fromisoformat(dropoff),
        fare_amount,
        trip_distance,
        pickup_zip,
    )


CSV_STRING_COLUMNS = [
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "fare_amount",
    "trip_distance",
    "pickup_zip",
    "dropoff_zip",
]


def test_cast_raw_trip_columns_converts_csv_strings_to_typed_columns(spark):
    # Auto Loader が CSV から取り込んだ直後は、すべて文字列カラムになっている。
    rows = [
        ("2026-01-01 10:00:00", "2026-01-01 10:15:00", "30.0", "5.0", "10001", "10002"),
    ]
    df = spark.createDataFrame(rows, CSV_STRING_COLUMNS)
    assert dict(df.dtypes)["fare_amount"] == "string"

    result = cast_raw_trip_columns(df).collect()[0]

    assert result["tpep_pickup_datetime"] == datetime.fromisoformat("2026-01-01T10:00:00")
    assert result["tpep_dropoff_datetime"] == datetime.fromisoformat("2026-01-01T10:15:00")
    assert result["fare_amount"] == pytest.approx(30.0)
    assert result["trip_distance"] == pytest.approx(5.0)
    assert result["pickup_zip"] == 10001
    assert result["dropoff_zip"] == 10002


def test_add_trip_metrics_computes_expected_values(spark):
    rows = [make_trip("2026-01-01T10:00:00", "2026-01-01T10:15:00", 30.0, 5.0)]
    df = spark.createDataFrame(rows, RAW_COLUMNS)

    result = add_trip_metrics(df).collect()[0]

    assert result["pickup_date"].isoformat() == "2026-01-01"
    assert result["trip_minutes"] == pytest.approx(15.0)
    assert result["fare_per_mile"] == pytest.approx(6.0)


def test_quality_expectations_drop_invalid_rows(spark):
    rows = [
        make_trip("2026-01-01T10:00:00", "2026-01-01T10:15:00", 30.0, 5.0),  # valid
        make_trip("2026-01-01T10:00:00", "2026-01-01T10:15:00", 0.0, 5.0),  # fare <= 0
        make_trip("2026-01-01T10:00:00", "2026-01-01T10:15:00", 30.0, 0.0),  # distance <= 0
        make_trip("2026-01-01T10:15:00", "2026-01-01T10:00:00", 30.0, 5.0),  # dropoff <= pickup
    ]
    df = spark.createDataFrame(rows, RAW_COLUMNS)

    condition = " AND ".join(f"({expr})" for expr in QUALITY_EXPECTATIONS.values())
    filtered = df.filter(F.expr(condition))

    assert filtered.count() == 1


def test_aggregate_daily_groups_by_date_and_zip(spark):
    rows = [
        make_trip("2026-01-01T10:00:00", "2026-01-01T10:15:00", 30.0, 5.0, pickup_zip=10001),
        make_trip("2026-01-01T11:00:00", "2026-01-01T11:10:00", 20.0, 2.0, pickup_zip=10001),
        make_trip("2026-01-02T09:00:00", "2026-01-02T09:20:00", 40.0, 8.0, pickup_zip=10002),
    ]
    df = add_trip_metrics(spark.createDataFrame(rows, RAW_COLUMNS))

    result = {
        (row["pickup_date"].isoformat(), row["pickup_zip"]): row
        for row in aggregate_daily(df).collect()
    }

    same_day = result[("2026-01-01", 10001)]
    assert same_day["trip_count"] == 2
    assert same_day["avg_fare"] == pytest.approx(25.0)

    other_day = result[("2026-01-02", 10002)]
    assert other_day["trip_count"] == 1
    assert other_day["avg_fare"] == pytest.approx(40.0)
