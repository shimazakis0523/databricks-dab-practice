"""gold_qa_agent の MLflow ResponsesAgent 実装。

gold テーブル（trips_daily_gold）の集計データを、登録時にスナップショットとして
バンドルし（load_context で読み込む）、推論時は Databricks の Foundation
Model API（OpenAI 互換エンドポイント）に問い合わせて回答を生成する。

このモジュールは Databricks の Model Serving コンテナ（または mlflow>=3.1.0 /
openai がインストールされたノートブック環境）でのみ動作確認できる。

**プロンプト構築ロジック（SYSTEM_PROMPT_TEMPLATE / build_system_prompt /
build_messages）は gold_qa_agent.py と意図的に重複させている**（本来は
`from gold_qa_agent import build_messages` として import する設計だったが、
実際にワークスペースへデプロイしたところ
`ModuleNotFoundError: No module named 'gold_qa_agent'` になった。
「models from code」パターンでは、mlflow がこのファイルを解析する時点で
`code_paths`（notebooks/register_gold_qa_agent.py の code_paths=[AGENTS_DIR]）
による sys.path 設定がまだ効いておらず、登録時の Notebook では別の目的で
手動 sys.path.insert 済みだったために偶然動いてしまい、この問題がデプロイ
段階まで見逃されていた）。mlflow の code_paths の内部的な配置場所・
タイミングに依存する外部ファイル import は壊れやすいと判断し、
Serving コンテナで実行されるこのファイルは外部ファイルに一切依存しない
自己完結した形にした。**ロジックを変更する場合は gold_qa_agent.py と
両方を同じ内容に更新すること**（gold_qa_agent.py 側は
tests/test_gold_qa_agent.py でユニットテストする; このファイル側は
ワークスペースでの実デプロイでしか動作確認できない）。
`rows_to_context` は登録 Notebook 側でのみ使うため、gold_qa_agent.py に
残したまま複製していない。

「models from code」パターンでログする前提のため、このファイルの末尾で
`mlflow.models.set_model(...)` を呼び出す（notebooks/register_gold_qa_agent.py
が `mlflow.pyfunc.log_model(python_model=__file__, ...)` として参照する）。
"""

import os

import mlflow
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse
from openai import OpenAI

# gold_qa_agent.py の SYSTEM_PROMPT_TEMPLATE / build_system_prompt /
# build_messages と同一内容（意図的な重複。理由は上記モジュール docstring 参照）。
GOLD_TABLE = "workspace.nyctaxi.trips_daily_gold"

SYSTEM_PROMPT_TEMPLATE = """あなたは NYC タクシーの日次集計データ（{table}）を
分析するアシスタントです。以下はピックアップ ZIP コード別の集計データです。
ユーザーの質問に、このデータの範囲内で日本語で簡潔に答えてください。
データに無い情報は推測せず「データからはわかりません」と答えてください。

集計データ:
{context}
"""


def build_system_prompt(context: str) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(table=GOLD_TABLE, context=context)


def build_messages(question: str, context: str) -> list[dict]:
    return [
        {"role": "system", "content": build_system_prompt(context)},
        {"role": "user", "content": question},
    ]


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
        answer = response.choices[0].message.content

        # ResponsesAgentResponse に from_chat_completion のような変換
        # ヘルパーは存在しない（実際にワークスペースで実行して
        # `AttributeError: from_chat_completion` になったため判明した）。
        # 代わりに ResponsesAgent 自身が提供する create_text_output_item
        # （インストール済み mlflow==3.8.1 で実在を確認済み）でテキスト出力
        # アイテムを組み立て、output に渡す。
        output_item = self.create_text_output_item(text=answer, id=response.id)
        # ResponsesAgentResponse 自体にもトップレベルの id が必須（Responses API
        # の仕様）。省略すると実ワークスペースで Playground/API 呼び出し時に
        # "id is a required field" のスキーマ検証エラーになったため判明した。
        return ResponsesAgentResponse(output=[output_item], id=response.id)


mlflow.models.set_model(GoldQAResponsesAgent())
