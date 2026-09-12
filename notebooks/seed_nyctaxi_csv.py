# Databricks notebook source
# MAGIC %md
# MAGIC # ランディングゾーンへの CSV 投入（シードスクリプト）
# MAGIC
# MAGIC 実際の現場では、外部システムがストレージに CSV ファイルを置き、
# MAGIC Auto Loader がそれを増分で取り込むという構成が多くあります。
# MAGIC このノートブックはその「外部システムが CSV を置く」動作を模擬し、
# MAGIC `samples.nyctaxi.trips` から一部を抜き出して
# MAGIC Unity Catalog Volume（ランディングゾーン）に CSV として書き出します。
# MAGIC
# MAGIC - 1 回実行すれば `nyctaxi_pipeline` の Auto Loader が読み取れる状態になります。
# MAGIC - 複数回実行すると新しいファイルが追加され、
# MAGIC   Auto Loader が「前回取り込み済みの分はスキップし、新しいファイルだけ取り込む」
# MAGIC   様子を確認できます。

# COMMAND ----------

LANDING_PATH = "/Volumes/workspace/nyctaxi/landing"

# サーバーレス枠を圧迫しないよう件数は絞る
df = spark.read.table("samples.nyctaxi.trips").limit(2000)

# 複数ファイルに分割して書き出す = 複数の CSV が届く現場を再現
(
    df.repartition(4)
    .write.format("csv")
    .mode("append")
    .option("header", "true")
    .save(LANDING_PATH)
)

print(f"Wrote {df.count()} rows to {LANDING_PATH}")
