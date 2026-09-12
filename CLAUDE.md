# databricks-dab-practice への変更ガイド

## メタルール: 指摘を受けたら「直す」で終わらせない

### 適用対象の切り分け（新規依頼 vs 不備の指摘）

このメタルールは「不備の指摘」にのみ適用する。「依頼側起因の変更」（新しい
機能・仕様の追加、単なる scope 拡張）には適用しない。判定基準:

| 種類 | 判定基準 | 対応 |
| --- | --- | --- |
| 依頼側起因の変更 | 「以前からそうあるべきだった」という前提（明示/暗黙のルール・過去の約束）が無い、純粋な新規要求 | 通常どおり実装する。根本原因分析は不要（何も壊れていないため） |
| 不備の指摘 | 「既にそうなっているはず」という既存の前提・ルールが破られていた | 下記の3ステップを適用する |

迷ったら自問する: **「今回の指摘がなければ、同じ形の問題が今後も再発するか？」**
YES なら不備の指摘として扱い、NO なら単なる新規依頼として扱う。

### 不備の指摘に対する3ステップ

ユーザーや自分自身のレビューで欠陥（ドキュメントの欠落・設定ミス・誤った前提など）
を見つけたら、その場しのぎの修正だけで終えてはならない。**指摘されるたびに
同じ3ステップを、指示されなくても自分から実行する**:

1. **根本原因分析** — なぜ見逃したのか。どのプロセス・チェックが機能して
   いなかったのかを具体的に特定する（例:「ハーネスがファイルの存在しか
   見ておらず、中身の値までは見ていなかった」）
2. **フィードフォワードの更新** — 同じ根本原因が今後別の形で再発しないよう、
   このファイル（CLAUDE.md）にルールを追記する。個別の欠陥だけでなく、
   その欠陥を生んだ**プロセス上の穴**を塞ぐ記述にする
3. **ハーネスの更新** — 可能な限り、その欠陥のクラスを機械的に検知できる
   テストを追加・強化する。「今回のインスタンス」だけでなく「同じ形の欠陥」
   を広く拾えるようにする

この3ステップは、ユーザーに「フィードフォワードとハーネスを見直して」と
言われる前に、欠陥を修正するのと同じタイミングで自発的に行うこと。
「わかりました、直します」で終える対応は不十分とみなす。

## 構成変更・機能拡張をしたら README.md も必ず見直す

`resources/*.yml`・`pipelines/*.py`・`notebooks/*.py` の追加/削除/挙動変更を行った場合、
同じコミット（PR）で `README.md` の以下も更新すること:

- **「構成」セクションのファイルツリー** — 追加/削除したファイルを反映する
- **「このプロジェクトで検証している POC」の表** — 新しい検証観点が増えたら追記する
- **「全体構成図」の Mermaid フローチャート** — データの流れやトリガー関係が変わったら図も直す
- 該当するセクション本文（実行方法・注意点など）

「ファイルが存在する」レベルの同期だけでなく、**設定ファイルの中身の値**が
人間向けドキュメントとして正しく転記されているかも同じ基準で見直すこと
（例: `resources/groups.json` の `entitlements` 配列の値そのものが、
README の権限テーブルに反映されているか）。この観点は
`tests/test_groups_json_sync.py` で機械的にもチェックされる。
新しく「設定ファイルの値が人間可読なドキュメントとして意味を持つ」ケースが
増えたら、同様の内容同期テストを追加すること（ファイル存在チェックの
`test_readme_sync.py` だけでは不十分）。

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
- Lakeview ダッシュボード（`dashboards/*.lvdash.json`）は `databricks bundle
  validate` では JSON 構文しか検証されず、Lakeview 固有のスキーマ規約
  （例: 単一クエリウィジェットの `queries[].name` は固定で `main_query` に
  する必要がある、table ウィジェットの `encodings.columns` の `type` は
  日付列なら `"datetime"` ではなく `"date"` + `dateTimeFormat` を使う必要が
  あるなど、**フィールドの存在だけでなく値そのものが Lakeview の許容する
  ものか**、など）は実際にワークスペースへデプロイしてレンダリングするまで
  検知できない。「`type` フィールドがあるか」だけをチェックしても、値が
  無効なら結局実ワークスペースで "Invalid widget definition is imported"
  になる（実際に一度これで見逃した）。手書きで `.lvdash.json` を追加・変更
  した場合は、既知の規約違反を機械的にチェックする
  `tests/test_dashboard_conventions.py` を必ず通し、実ワークスペースでの
  表示確認をユーザーに依頼すること。新しい描画エラーに遭遇したら、
  「フィールドの存在」ではなく「値の妥当性」まで踏み込んだ検証として
  同テストに追記して再発を防ぐ。
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
- SQL Warehouse ID のような**ワークスペースごとに異なる値**は、リソース定義に
  文字列直書きせず `databricks.yml` の `variables` で管理する
  （`resources/nyctaxi_dashboard.yml` の `warehouse_id: ${var.warehouse_id}`
  を参照）。`--var` フラグや `BUNDLE_VAR_<name>` 環境変数で上書きでき、
  別のワークスペースへの移植性が上がる。一方、`catalog` / `schema` のような、
  このバンドルの設計上どのワークスペースでも同じ値になる想定のものは
  文字列リテラルのままでよい（変数化するかどうかは「環境によって変わる値か」
  で判断する）。
    - **このルールはワークスペース URL（`workspace.host`）にも同様に適用する。**
      過去に `databricks.yml` の `targets.dev.workspace.host` へワークスペース URL
      を直書きしたままにしていたことがあり、このバンドルを別のワークスペース
      （本番導入プロジェクトなど）に持ち込む際にエラー・誤デプロイの原因になる
      ところだった。根本原因は、このルールを「一般論」としてしか書いておらず、
      どのフィールドが対象かを機械的にチェックしていなかったこと。`workspace.host`
      は `variables` にせず、そもそも `databricks.yml` に書かない（`DATABRICKS_HOST`
      環境変数または CLI プロファイルで指定する）方式にした。新しく
      「環境で決まる固定値」をコード中に見つけたら、このルールに従い
      `variables` 化するか設定ファイルから追い出すかを検討し、
      `tests/test_no_hardcoded_workspace_values.py` のように機械的に
      検知できるテストを追加すること。
