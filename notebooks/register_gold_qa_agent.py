# Databricks notebook source
# MAGIC %md
# MAGIC # gold_qa_agent の登録
# MAGIC
# MAGIC `trips_daily_gold` の集計データをスナップショットとして取得し、
# MAGIC `agents/gold_qa_responses_agent.py`（MLflow ResponsesAgent）に
# MAGIC バンドルしたうえで、Unity Catalog にモデルとして登録する。
# MAGIC
# MAGIC 登録後に表示される **Version** の値を、
# MAGIC `databricks.yml` の `variables.gold_qa_agent_model_version` に設定し、
# MAGIC 再デプロイすると `resources/gold_qa_agent_serving.yml` の
# MAGIC Model Serving エンドポイントがこのバージョンを配信する。

# COMMAND ----------

# MAGIC %pip install --quiet mlflow>=3.1.0 openai
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import os

import mlflow

AGENTS_DIR = os.path.join(os.path.dirname(os.getcwd()), "agents")
GOLD_TABLE = "workspace.nyctaxi.trips_daily_gold"
REGISTERED_MODEL_NAME = "workspace.nyctaxi.gold_qa_agent"

# COMMAND ----------

# gold テーブルを ZIP ごとに集計し、agents/gold_qa_agent.py の
# rows_to_context と同じ形の dict に変換する。
rows = (
    spark.sql(
        f"""
        SELECT
            pickup_zip,
            SUM(trip_count) AS total_trips,
            ROUND(AVG(avg_fare), 2) AS avg_fare,
            ROUND(AVG(avg_distance), 2) AS avg_distance,
            ROUND(AVG(avg_trip_minutes), 1) AS avg_trip_minutes
        FROM {GOLD_TABLE}
        GROUP BY pickup_zip
        ORDER BY total_trips DESC
        LIMIT 10
        """
    )
    .collect()
)
rows = [row.asDict() for row in rows]

import sys

sys.path.insert(0, AGENTS_DIR)
from gold_qa_agent import rows_to_context  # noqa: E402

gold_context_text = rows_to_context(rows)
print(gold_context_text)

# COMMAND ----------

gold_context_path = "/tmp/gold_qa_agent_context.txt"
with open(gold_context_path, "w", encoding="utf-8") as f:
    f.write(gold_context_text)

# mlflow.pyfunc.log_model() は登録直後に「入力例に対する予測」を自動実行して
# 検証する。GoldQAResponsesAgent.load_context は DATABRICKS_HOST/TOKEN を
# 環境変数から読むが、これらは本来 Model Serving 側の environment_vars から
# 渡す想定で、登録時のこの Notebook 環境には無い。そのままだと検証の predict()
# 呼び出しで KeyError になり登録自体が失敗するため、Notebook 自身の実行コンテキスト
# から一時的に同じ環境変数を設定しておく。これはついでに、登録時点で実際に
# Foundation Model API を1回呼び出す形になり、エージェント全体の簡易的な
# スモークテストにもなる。
os.environ["DATABRICKS_HOST"] = "https://" + spark.conf.get("spark.databricks.workspaceUrl")
os.environ["DATABRICKS_TOKEN"] = (
    dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().getOrElse(None)
)

mlflow.set_registry_uri("databricks-uc")

with mlflow.start_run(run_name="gold_qa_agent"):
    model_info = mlflow.pyfunc.log_model(
        name="gold_qa_agent",
        python_model=os.path.join(AGENTS_DIR, "gold_qa_responses_agent.py"),
        code_paths=[AGENTS_DIR],
        artifacts={"gold_context": gold_context_path},
        registered_model_name=REGISTERED_MODEL_NAME,
        pip_requirements=["mlflow>=3.1.0", "openai"],
    )

print(f"Registered {REGISTERED_MODEL_NAME}, version={model_info.registered_model_version}")
