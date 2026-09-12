# databricks-dab-practice への変更ガイド

## 構成変更・機能拡張をしたら README.md も必ず見直す

`resources/*.yml`・`pipelines/*.py`・`notebooks/*.py` の追加/削除/挙動変更を行った場合、
同じコミット（PR）で `README.md` の以下も更新すること:

- **「構成」セクションのファイルツリー** — 追加/削除したファイルを反映する
- **「このプロジェクトで検証している POC」の表** — 新しい検証観点が増えたら追記する
- **「全体構成図」の Mermaid フローチャート** — データの流れやトリガー関係が変わったら図も直す
- 該当するセクション本文（実行方法・注意点など）

これは `tests/test_readme_sync.py` で機械的にもチェックされる
（`resources/*.yml` / `pipelines/*.py` / `notebooks/*.py` のファイル名が
README.md 本文のどこかに出現しているかを検証するだけの簡易チェックだが、
更新し忘れの一次検知として機能する）。CI の `test` ジョブに含まれるため、
README を更新し忘れると CI が落ちる。

## その他の開発ルール

- Unity Catalog のカタログ/スキーマ参照（`catalog` / `schema` /
  `catalog_name` / `schema_name`）は文字列リテラルで統一する。理由と経緯は
  README の「開発時の注意点」を参照。`tests/test_resource_conventions.py`
  がこれも機械的にチェックする。
- パイプラインの変換ロジックは `dlt` に依存しない純粋関数として
  `pipelines/transforms.py` に切り出し、`tests/test_transforms.py` で
  pytest テストする（`nyctaxi_pipeline.py` 自体は Databricks 実行環境でしか
  import できないため）。
- コミット・push 前にローカルで `pytest tests/ -v` を実行して確認する。
- 組織のロール・権限は「現在の自分がたまたま admin だから省略してよい」で判断しない。
  ロールごとの権限は常にコードとして実装する（`resources/nyctaxi_permissions_job.yml` +
  `notebooks/grant_role_access.py` の SQL GRANT）。
- Unity Catalog のスキーマを `resources.schemas` としてバンドル管理しようとすると、
  そのスキーマが既にバンドル管理外で作成済みの場合 `SCHEMA_ALREADY_EXISTS` で
  デプロイが失敗する。既存データを保持したまま権限だけ管理したい場合は、
  `resources.schemas` の `grants` ではなく、明示的な SQL GRANT（べき等な
  Notebook + 手動実行 Job）で運用する。
- 「グループやユーザーは DAB / アカウントコンソールで管理できないから、手動作成でよい」
  で済ませない。Free Edition のようにアカウントコンソール・SCIM がない環境でも、
  ワークスペース単位の SCIM Groups API（`/api/2.0/preview/scim/v2/Groups`）を
  直接叩けば自動化できる。`resources/groups.json` + `scripts/ensure_groups.py`
  のパターン（CI の deploy ジョブから自動実行）を踏襲する。
- ワークスペースの「Add user」画面にあるユーザーごとの entitlements トグル
  （Workspace access / Databricks SQL access など）は、データ権限（grants）とは
  別系統のガバナンスになりがちなので使わない。entitlements もグループに
  設定し（`resources/groups.json` の `entitlements`）、ユーザーは
  グループ経由で継承させることでガバナンスを一本化する。
- IaC（`resources/groups.json`）に定義されていないグループが存在してはならない、
  という前提を `scripts/audit_undeclared_groups.py` で機械的に検知・削除できる
  ようにしてある。ただし `admins` / `users` は Databricks のシステム予約
  グループなので、削除候補から常に除外する（ハードコードした保護リストに
  手を加えない）。CI（`.github/workflows/deploy.yml`）では現状 `--dry-run`
  付きで実行しており、実削除はしていない。実削除を CI から自動化する変更
  （`--dry-run` を外す）は、この Claude Code セッションの自動モード分類器が
  "Unverifiable Deletion Scope" として拒否し、`.claude/settings.local.json`
  への許可ルール追加もセッション自身では「Self-Modification」として拒否
  される。ユーザー本人がその設定ファイルを用意しない限り、この環境からは
  実削除版を commit/push できない。
- ユーザーへの直接付与（グループ経由でない）entitlements は検知はするが
  （`scripts/audit_user_entitlements.py`）自動修正はしない。ワークスペースの
  オーナー/管理者アカウントなど、正当な理由で直接権限を持つ場合があるため。
  このスクリプトは常に exit code 0 で終了する仕様を変えない。
- Databricks はユーザー作成時に最低1つの直接 entitlement（多くの場合
  `workspace-consume` = Consumer access）を要求し、これは回避できない。
  「グループ経由で継承させ、直接付与はゼロにする」という理想を額面通り
  実装しようとしない。`workspace-consume` は
  `scripts/audit_user_entitlements.py` の `UNAVOIDABLE_DIRECT_ENTITLEMENTS`
  として常に許容し、かつ `resources/groups.json` の全グループにも含めて
  グループ経由でカバーされるようにする、という二重の対策を踏襲する。
  監査レポートの文言は「グループでカバーされていない直接付与」だけを
  問題として示し、所属グループ自体が悪いように読める書き方をしない。
