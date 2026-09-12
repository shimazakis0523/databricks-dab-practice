"""pytest 共通フィクスチャ。

ローカル (local[1]) の SparkSession をテスト全体で使い回す。
Databricks 上の実行は不要 — CI 環境の PySpark だけで完結する。
"""

import pytest
from pyspark.sql import SparkSession


@pytest.fixture(scope="session")
def spark():
    session = (
        SparkSession.builder.master("local[1]")
        .appName("nyctaxi-pipeline-tests")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield session
    session.stop()
