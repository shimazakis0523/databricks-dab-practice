"""gold_qa_agent（Model Serving エンドポイント）に質問できる簡易 Streamlit UI。

Databricks Apps 上で実行する前提。認証は Databricks Apps のランタイムが
自動的に処理するため（app のサービスプリンシパルに対して
`resources/gold_qa_streamlit_app.yml` で serving_endpoint への
CAN_QUERY 権限を付与している）、このコード自身はトークンを扱わない。
"""

import os

import streamlit as st
from databricks_openai import DatabricksOpenAI

# resources/gold_qa_streamlit_app.yml の app resources の name（"gold_qa_agent"）に
# 対応する app.yaml の env.valueFrom 経由で、実際のエンドポイント名が渡される。
SERVING_ENDPOINT = os.environ["SERVING_ENDPOINT"]

st.set_page_config(page_title="gold_qa_agent", layout="centered")
st.title("NYC タクシー gold データ Q&A")
st.caption(f"Serving endpoint: {SERVING_ENDPOINT}")

question = st.text_area(
    "trips_daily_gold の集計データについて質問してください",
    value="トリップ数が一番多い ZIP はどこですか？",
    height=240,
)

if st.button("質問する") and question:
    client = DatabricksOpenAI()
    with st.spinner("回答を生成中..."):
        response = client.responses.create(
            model=SERVING_ENDPOINT,
            input=[{"role": "user", "content": question}],
        )
    st.write(response.output_text)
