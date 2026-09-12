"""gold_qa_agent が使うプロンプト構築ロジック（純粋関数）。

gold_qa_responses_agent.py（MLflow ResponsesAgent 実装）は mlflow / openai /
databricks 実行環境に依存するモジュールを import するため、ローカルでは
テストできない。ロジックの本体（gold テーブルの集計行を LLM 向けの
コンテキスト文字列に変換する処理、チャットメッセージの組み立て）はここに
純粋関数として切り出し、tests/test_gold_qa_agent.py でテストする
（pipelines/transforms.py と同じパターン）。
"""

GOLD_TABLE = "workspace.nyctaxi.trips_daily_gold"

SYSTEM_PROMPT_TEMPLATE = """あなたは NYC タクシーの日次集計データ（{table}）を
分析するアシスタントです。以下はピックアップ ZIP コード別の集計データです。
ユーザーの質問に、このデータの範囲内で日本語で簡潔に答えてください。
データに無い情報は推測せず「データからはわかりません」と答えてください。

集計データ:
{context}
"""


def rows_to_context(rows: list[dict]) -> str:
    """gold テーブルの集計行（dict のリスト）を LLM プロンプト用のテキストに変換する。"""
    if not rows:
        return "(データがありません)"
    lines = [
        f"- ZIP {row['pickup_zip']}: 件数={row['total_trips']}, "
        f"平均運賃=${row['avg_fare']}, 平均距離={row['avg_distance']}マイル, "
        f"平均乗車時間={row['avg_trip_minutes']}分"
        for row in rows
    ]
    return "\n".join(lines)


def build_system_prompt(context: str) -> str:
    """gold データのコンテキストを埋め込んだシステムプロンプトを組み立てる。"""
    return SYSTEM_PROMPT_TEMPLATE.format(table=GOLD_TABLE, context=context)


def build_messages(question: str, context: str) -> list[dict]:
    """ユーザーの質問と gold データのコンテキストから、チャットメッセージ配列を組み立てる。"""
    return [
        {"role": "system", "content": build_system_prompt(context)},
        {"role": "user", "content": question},
    ]
