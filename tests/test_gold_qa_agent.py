"""agents/gold_qa_agent.py のユニットテスト（Spark 不要・高速）。

gold_qa_responses_agent.py 自体は mlflow / openai / Databricks 実行環境が
無いと import できない（ResponsesAgent が実際のワークスペースの Model
Serving コンテナ内でしか動作確認できない）ため、テスト可能なプロンプト
構築ロジックは agents/gold_qa_agent.py に切り出してある。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from gold_qa_agent import (  # noqa: E402
    GOLD_TABLE,
    build_messages,
    build_system_prompt,
    rows_to_context,
)


def test_rows_to_context_formats_each_row():
    rows = [
        {
            "pickup_zip": 10001,
            "total_trips": 42,
            "avg_fare": 12.5,
            "avg_distance": 3.2,
            "avg_trip_minutes": 8.1,
        }
    ]

    context = rows_to_context(rows)

    assert "ZIP 10001" in context
    assert "件数=42" in context
    assert "$12.5" in context
    assert "3.2マイル" in context
    assert "8.1分" in context


def test_rows_to_context_handles_empty_rows():
    assert rows_to_context([]) == "(データがありません)"


def test_build_system_prompt_includes_table_name_and_context():
    prompt = build_system_prompt("(テストコンテキスト)")

    assert GOLD_TABLE in prompt
    assert "(テストコンテキスト)" in prompt


def test_build_messages_produces_system_and_user_messages():
    messages = build_messages("一番トリップ数が多い ZIP はどこですか？", "(コンテキスト)")

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "(コンテキスト)" in messages[0]["content"]
    assert messages[1] == {
        "role": "user",
        "content": "一番トリップ数が多い ZIP はどこですか？",
    }
