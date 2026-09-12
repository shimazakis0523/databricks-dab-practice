"""gold_qa_agent の MLflow ResponsesAgent 実装。

gold テーブル（trips_daily_gold）の集計データを、登録時にスナップショットとして
バンドルし（load_context で読み込む）、推論時は Databricks の Foundation
Model API（OpenAI 互換エンドポイント）に問い合わせて回答を生成する。

このモジュールは Databricks の Model Serving コンテナ（または mlflow>=3.1.0 /
openai がインストールされたノートブック環境）でのみ動作確認できる。テスト可能な
プロンプト構築ロジックは gold_qa_agent.py に切り出してあり、そちらは
tests/test_gold_qa_agent.py でユニットテストする。

「models from code」パターンでログする前提のため、このファイルの末尾で
`mlflow.models.set_model(...)` を呼び出す（notebooks/register_gold_qa_agent.py
が `mlflow.pyfunc.log_model(python_model=__file__, ...)` として参照する）。
"""

import os

import mlflow
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse
from openai import OpenAI

from gold_qa_agent import build_messages

# 基盤モデル（Foundation Model API）のエンドポイント名。Databricks が
# ワークスペース間で提供する pay-per-token のシステムエンドポイント名だが、
# ワークスペースのプラン/リージョンによって提供モデルが異なりうるため、
# 環境変数で上書きできるようにしておく（resources/gold_qa_agent_serving.yml
# の environment_vars 経由で渡す）。
FOUNDATION_MODEL_ENDPOINT_ENV = "GOLD_QA_FOUNDATION_MODEL_ENDPOINT"
DEFAULT_FOUNDATION_MODEL_ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"


class GoldQAResponsesAgent(ResponsesAgent):
    def load_context(self, context):
        with open(context.artifacts["gold_context"], encoding="utf-8") as f:
            self.gold_context = f.read()

        # DATABRICKS_HOST / DATABRICKS_TOKEN は
        # resources/gold_qa_agent_serving.yml の environment_vars から渡す
        # （ワークスペースごとに異なる値のため、コードに直書きしない）。
        host = os.environ["DATABRICKS_HOST"]
        token = os.environ["DATABRICKS_TOKEN"]
        self.client = OpenAI(base_url=f"{host}/serving-endpoints", api_key=token)
        self.model = os.environ.get(
            FOUNDATION_MODEL_ENDPOINT_ENV, DEFAULT_FOUNDATION_MODEL_ENDPOINT
        )

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        # request.input の各要素は dict ではなく Message オブジェクト
        # （属性アクセス）。実際にワークスペースで実行して
        # `TypeError: 'Message' object is not subscriptable` になったため判明した
        # （辞書アクセスできる例を紹介する記事もあるが、mlflow>=3.1.0 の
        # ResponsesAgentRequest ではこの形になる）。
        question = request.input[-1].content
        messages = build_messages(question, self.gold_context)

        response = self.client.chat.completions.create(model=self.model, messages=messages)

        return ResponsesAgentResponse.from_chat_completion(response)


mlflow.models.set_model(GoldQAResponsesAgent())
