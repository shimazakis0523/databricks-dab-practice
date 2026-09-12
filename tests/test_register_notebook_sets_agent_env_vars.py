"""notebooks/register_gold_qa_agent.py が、log_model 呼び出し前に
gold_qa_agent が必要とする環境変数を設定していることの静的チェック
（Spark 不要・高速）。

過去に踏んだ落とし穴の再発防止用:
`mlflow.pyfunc.log_model()` は登録直後に「入力例に対する予測」を自動実行して
検証する（＝登録時の Notebook 環境で一度 predict() が呼ばれる）。
`agents/gold_qa_responses_agent.py` の `load_context` は `DATABRICKS_HOST` /
`DATABRICKS_TOKEN` を環境変数から読むが、これらは本来 Model Serving 側の
`environment_vars` からのみ渡す想定だったため、登録時の Notebook 環境には
存在せず、実際に `gold_qa_agent_registration_job` の実行が
`KeyError: 'DATABRICKS_HOST'` で失敗したことがある。

このテストは、Notebook 内で該当の環境変数が
`mlflow.pyfunc.log_model(` 呼び出しより前に設定されているかを、
テキストベースで簡易チェックする（実際に Notebook を実行して確かめる
代わりの、機械的な一次検知）。
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "register_gold_qa_agent.py"

REQUIRED_ENV_VAR_ASSIGNMENTS = [
    'os.environ["DATABRICKS_HOST"]',
    'os.environ["DATABRICKS_TOKEN"]',
]


def test_register_notebook_sets_env_vars_before_log_model():
    text = NOTEBOOK.read_text(encoding="utf-8")

    # コメント中の説明文にも "mlflow.pyfunc.log_model(" という文字列が
    # 含まれるため、実際の呼び出し行（代入式になっている行）だけを狙う。
    log_model_call = "= mlflow.pyfunc.log_model("
    log_model_index = text.find(log_model_call)
    assert log_model_index != -1, (
        "notebooks/register_gold_qa_agent.py に"
        f" `{log_model_call}` の呼び出しが見つかりません。"
    )

    missing_or_late = []
    for assignment in REQUIRED_ENV_VAR_ASSIGNMENTS:
        idx = text.find(assignment)
        if idx == -1:
            missing_or_late.append(f"{assignment} が見つかりません")
        elif idx > log_model_index:
            missing_or_late.append(
                f"{assignment} が mlflow.pyfunc.log_model(...) より後に設定されています"
            )

    assert not missing_or_late, (
        "log_model() は登録直後に predict() を自動実行して検証するため、"
        " gold_qa_agent が読む環境変数は log_model() 呼び出しより前に"
        " 設定しておく必要があります（さもないと実ワークスペースで"
        " KeyError になります）:\n" + "\n".join(missing_or_late)
    )
