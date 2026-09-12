#!/usr/bin/env bash
# resources/groups.txt に列挙されたワークスペースグループが存在しない場合のみ作成する。
#
# Databricks Free Edition はアカウントコンソール/SCIM 同期が使えないため
# `databricks account groups ...` は使えない。代わりに、ワークスペース単位の
# SCIM Groups API (/api/2.0/preview/scim/v2/Groups) を Databricks CLI の
# 汎用 `databricks api` 経由で叩く。DATABRICKS_HOST / DATABRICKS_TOKEN の
# 環境変数がすでに設定されている前提（CI の deploy ジョブと同じ認証）。
#
# 使い方: DATABRICKS_HOST=... DATABRICKS_TOKEN=... ./scripts/ensure_groups.sh

set -euo pipefail

GROUPS_FILE="$(dirname "$0")/../resources/groups.txt"

while IFS= read -r group_name || [ -n "$group_name" ]; do
  # 空行・コメント行はスキップ
  [ -z "$group_name" ] && continue
  case "$group_name" in \#*) continue ;; esac

  encoded_name=$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))" "$group_name")

  existing_count=$(
    databricks api get "/api/2.0/preview/scim/v2/Groups?filter=displayName%20eq%20%22${encoded_name}%22" \
      | python3 -c "import json, sys; print(json.load(sys.stdin).get('totalResults', 0))"
  )

  if [ "$existing_count" -gt 0 ]; then
    echo "[ensure_groups] '${group_name}' は既に存在します。スキップします。"
    continue
  fi

  echo "[ensure_groups] '${group_name}' を作成します。"
  payload=$(python3 -c "
import json, sys
print(json.dumps({
    'schemas': ['urn:ietf:params:scim:schemas:core:2.0:Group'],
    'displayName': sys.argv[1],
}))
" "$group_name")

  databricks api post /api/2.0/preview/scim/v2/Groups --json "$payload" >/dev/null
  echo "[ensure_groups] '${group_name}' を作成しました。"
done < "$GROUPS_FILE"
