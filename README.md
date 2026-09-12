# databricks-dab-practice

Databricks Asset Bundles (DAB) の学習用プロジェクトです。
NYC タクシーデータのメダリオンパイプラインを DAB で管理します。

## 構成

```
.
├── databricks.yml                  # バンドル定義（バンドル名 / ターゲット）
├── resources/
│   ├── nyctaxi_landing.yml         # ランディング用 Volume 定義
│   ├── nyctaxi_pipeline.yml        # パイプライン定義（メダリオン構成）
│   ├── nyctaxi_job.yml             # Job 定義（パイプラインを起動）
│   └── nyctaxi_seed_job.yml        # Job 定義（CSV をランディングゾーンへ投入）
├── notebooks/
│   └── seed_nyctaxi_csv.py         # CSV シード投入用 Notebook
├── pipelines/
│   ├── nyctaxi_pipeline.py         # bronze(Auto Loader) / silver / gold を宣言する Python（dlt 依存）
│   └── transforms.py               # 変換ロジック本体（純粋関数、pytest でテスト可能）
├── tests/
│   ├── conftest.py                    # ローカル SparkSession フィクスチャ
│   ├── test_transforms.py             # transforms.py のユニットテスト
│   └── test_resource_conventions.py   # resources/*.yml の命名規則チェック（再発防止）
└── requirements-test.txt           # テスト用依存関係（pyspark, pytest, PyYAML）
```

- Pipeline: `nyctaxi_pipeline` — Lakeflow Declarative Pipelines（旧 Delta Live Tables）
- Job: `nyctaxi_job` — `pipeline_task` で上記パイプラインを起動（ランディングゾーンへの CSV 到着を検知する File arrival トリガー）
- Job: `nyctaxi_seed_job` — ランディングゾーンへ CSV を投入する（手動実行用）
- Free Edition はサーバーレスコンピュートのみ利用できるため、クラスタ定義は含めていません

## データパイプライン（nyctaxi_pipeline）

実際の現場でよくある「外部システムがストレージに CSV を置き、それを増分で取り込む」
という構成を、Unity Catalog Volume と Auto Loader で再現しています。
入力データ自体は `samples.nyctaxi.trips`（Databricks に最初から用意されているサンプル）から
CSV として書き出したものです。

| レイヤ | テーブル | 内容 |
| --- | --- | --- |
| Bronze | `trips_bronze` | Auto Loader (`cloudFiles`) で landing volume の CSV を増分取り込み（すべて文字列） |
| Silver | `trips_silver` | 文字列カラムを型変換し、品質チェック（運賃・距離・時刻）で不正行を除外。乗車時間と距離あたり運賃を付与 |
| Gold | `trips_daily_gold` | 乗車日 × 乗車 ZIP ごとの件数・平均運賃・平均距離を集計 |

- 出力先は `workspace.nyctaxi` スキーマ（`resources/nyctaxi_pipeline.yml` の `catalog` / `schema`）
- ランディングゾーンは `resources/nyctaxi_landing.yml` で定義する Volume
  `/Volumes/workspace/nyctaxi/landing`。`catalog_name` / `schema_name` は
  パイプラインと同じく文字列で直接指定しています
  （`mode: development` はバンドル管理の `schemas` リソースの物理名を
  `dev_<user>_nyctaxi` のようにリネームしてしまうため、あえて schemas
  リソースにはせず、パイプラインが作成する `nyctaxi` スキーマをそのまま参照しています）
- 品質ルールは `@dlt.expect_all_or_drop` で定義。違反行は取り込まれず、パイプライン画面でドロップ件数を確認できます
- CSV は Auto Loader の既定動作どおり、いったんすべて文字列として Bronze に入り、
  Silver に渡す前に `cast_raw_trip_columns`（`pipelines/transforms.py`）で型変換します

### 実行方法

1. **CSV を投入する** — `nyctaxi_seed_job` を **Run**。`samples.nyctaxi.trips` から
   2,000 件を抜き出し、4 ファイルに分けてランディングゾーンへ CSV として書き出します。
2. **パイプラインを実行する** — `nyctaxi_pipeline`（または `nyctaxi_job`）を **Run**。
   Auto Loader がランディングゾーンの CSV を取り込み、bronze → silver → gold を更新します。

```bash
databricks bundle run nyctaxi_seed_job -t dev   # CSV をランディングゾーンへ投入
databricks bundle run nyctaxi_pipeline -t dev   # パイプラインを直接実行
databricks bundle run nyctaxi_job -t dev        # Job 経由で実行
```

`nyctaxi_seed_job` をもう一度 **Run** すると、ランディングゾーンに新しい CSV が
追加で書き込まれます。その状態で `nyctaxi_pipeline` を再実行すると、
Auto Loader が「前回取り込み済みのファイルはスキップし、新しいファイルだけを取り込む」
様子を確認できます（bronze テーブルの行数が差分だけ増える）。

### 自動実行（File arrival トリガー）

`nyctaxi_job` は `pipeline_task` でパイプライン ID を参照しており、
ID はバンドルのデプロイ時に `${resources.pipelines.nyctaxi_pipeline.id}` で自動解決されます。

手動で Run する代わりに、ランディングゾーン（`/Volumes/workspace/nyctaxi/landing/`）に
新しい CSV が届いたことを検知して自動的に起動する **File arrival トリガー** を設定しています。
`nyctaxi_seed_job` を実行して CSV を投入すると、`nyctaxi_job` → `nyctaxi_pipeline` が
自動的に起動し、手動で Run しなくても取り込みが行われます。

```yaml
trigger:
  file_arrival:
    url: /Volumes/workspace/nyctaxi/landing/
    min_time_between_triggers_seconds: 60
    wait_after_last_change_seconds: 60
```

- `min_time_between_triggers_seconds`: 短時間に何度もファイルが来ても、この間隔以上空けてから起動する
- `wait_after_last_change_seconds`: 最後のファイル変更からこの秒数だけ待ってから起動する（書き込み完了を待つため）

> **注意**: `mode: development` は既定でスケジュール/トリガーを一時停止（PAUSED）状態で
> デプロイする。DAB が管理する Job はワークスペース UI から直接 Resume できない
> （「Connected to Declarative Automation Bundles」と表示され、`Edit trigger` /
> `Resume` / `Delete` が非活性になる）ため、`databricks.yml` の `dev` ターゲットに
> `presets.trigger_pause_status: UNPAUSED` を設定してデプロイ時から有効化した状態にしている。
>
> 有効化すると、ファイルが届くたびにサーバーレスが起動して実行されるため、
> `nyctaxi_seed_job` を連続実行するとサーバーレス枠を早く消費する点に注意すること。

実行後、カタログエクスプローラの `workspace > nyctaxi` に3つのテーブルが作成されます。
SQL エディタから確認できます。

```sql
SELECT * FROM workspace.nyctaxi.trips_daily_gold ORDER BY trip_count DESC LIMIT 20;
```

### 変換ロジックとユニットテスト

`dlt` モジュールは Databricks の Lakeflow Declarative Pipelines 実行環境でしか
import できないため、`nyctaxi_pipeline.py` そのものは手元や CI で直接テストできません。
そこで変換ロジック（型変換、乗車時間・距離あたり運賃の計算、品質ルール、日次集計）を
`pipelines/transforms.py` に純粋関数として切り出し、`nyctaxi_pipeline.py` からは
通常の Python import で参照する構成にしています。

```python
# nyctaxi_pipeline.py
from transforms import (
    QUALITY_EXPECTATIONS,
    add_trip_metrics,
    aggregate_daily,
    cast_raw_trip_columns,
)
```

Lakeflow Declarative Pipelines はパイプラインのルートディレクトリを自動的に
`sys.path` へ追加するため、この import はデプロイ後もそのまま動作します
（`resources/nyctaxi_pipeline.yml` の `libraries` は `glob` で
`pipelines/**` をまとめて配置しています）。

`pipelines/transforms.py` は `tests/test_transforms.py` からローカルの PySpark で
テストできます（CSV 由来の文字列カラムを `cast_raw_trip_columns` が正しく型変換するか、
といったケースも含みます）。

```bash
pip install -r requirements-test.txt
pytest tests/ -v
```

## デプロイ方法は3通り

- **A. ワークスペース UI（Bundle エディタ）からデプロイ** — ローカルに何もインストール不要。おすすめ
- **B. ローカル PC の Databricks CLI からデプロイ** — CI/CD や本番運用向け
- **C. GitHub Actions からデプロイ（CI/CD）** — `main` に push すると自動で validate / deploy

---

## A. ワークスペース UI からデプロイする（Databricks Free Edition）

ワークスペース上の **Git フォルダ** にこのリポジトリを取り込み、Bundle エディタから
ターゲットの切り替え・デプロイ・実行まで行えます。ローカルへの CLI インストールは不要です。

### 1. Git フォルダとしてリポジトリを取り込む

1. ワークスペース左メニューの **Workspace** を開きます。
2. 自分のユーザーフォルダで **Create > Git folder** を選択します。
3. Git repository URL に `https://github.com/shimazakis0523/databricks-dab-practice` を入力します。
4. Git provider が `GitHub` になっていることを確認し、**Create Git folder** をクリックします。
5. 作成後、ブランチを `claude/upbeat-albattani-x2cbei`（または main にマージ済みならそのまま）に切り替えます。

> プライベートリポジトリの場合は、事前に **Settings > Linked accounts** で GitHub の
> パーソナルアクセストークンを登録しておく必要があります。

### 2. Bundle エディタを開く

Git フォルダ内の `databricks.yml` をクリックすると、バンドルとして認識され
Bundle エディタが開きます。左側にバンドルのリソース（`nyctaxi_pipeline` など）が表示されます。

### 3. ターゲットを選んでデプロイする

1. エディタ右上のターゲット選択で **dev** を選びます。
2. **Deploy** をクリックします。
3. デプロイログが表示され、完了すると `[dev <ユーザー名>] nyctaxi_pipeline` などが作成されます。

### 4. Job / Pipeline を実行する

1. リソース一覧から `nyctaxi_seed_job` を選び、**Run** をクリックします（CSV をランディングゾーンへ投入）。
2. 続けて `nyctaxi_pipeline`（または `nyctaxi_job`）を **Run** します。
3. **ジョブとパイプライン** 画面から実行履歴・結果を確認できます。

### 5. 変更を GitHub に戻す

エディタ上で編集した内容は Git フォルダの UI（**Commit & push**）から GitHub に反映できます。

---

## B. ローカル PC の Databricks CLI からデプロイする

### 1. Free Edition のアカウントを作成する

1. https://www.databricks.com/learn/free-edition にアクセスします。
2. サインアップし、ワークスペースにログインします。
3. ブラウザのアドレスバーに表示されるワークスペース URL
   （例: `https://dbc-xxxxxxxx-xxxx.cloud.databricks.com`）を控えます。

### 2. Databricks CLI をインストールする

```bash
# macOS / Linux (Homebrew)
brew tap databricks/tap
brew install databricks

# または汎用インストーラ
curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh

# バージョン確認（DAB は v0.205 以降が必要）
databricks --version
```

### 3. 認証を設定する

```bash
databricks auth login --host https://dbc-b1c4d17f-58d9.cloud.databricks.com
```

ブラウザが開くので OAuth でログインします。プロファイル名を聞かれたら任意の名前
（例: `free-edition`）を入力します。設定は `~/.databrickscfg` に保存されます。

### 4. ワークスペース URL を確認する

`databricks.yml` の `targets.dev.workspace.host` には、このプロジェクトで使う
Free Edition のワークスペース URL を設定済みです。別のワークスペースを使う場合のみ書き換えてください。

```yaml
targets:
  dev:
    workspace:
      host: https://dbc-b1c4d17f-58d9.cloud.databricks.com
```

### 5. バンドルを検証する

```bash
databricks bundle validate -t dev
```

（プロファイルを明示する場合は `-p free-edition` を付けます。）

### 6. デプロイする

```bash
databricks bundle deploy -t dev
```

成功すると、ワークスペースの
`/Workspace/Users/<your-email>/.bundle/databricks-dab-practice/dev/` 配下にファイルが配置され、
`[dev <your-name>] nyctaxi_pipeline` などの Job / Pipeline が作成されます。

### 7. Job / Pipeline を実行する

```bash
databricks bundle run nyctaxi_seed_job -t dev   # CSV をランディングゾーンへ投入
databricks bundle run nyctaxi_pipeline -t dev   # パイプラインを実行
```

Databricks 画面の **ジョブとパイプライン** からも実行・結果確認ができます。

### 8. 後片付け(任意)

```bash
databricks bundle destroy -t dev
```

デプロイした Job・Pipeline・Volume とファイルが削除されます。

## C. GitHub Actions から自動デプロイする（CI/CD）

`.github/workflows/deploy.yml` に、以下を行う GitHub Actions ワークフローを用意しています。

- Pull Request 作成時・`main` への push 時: `pytest tests/`（ユニットテスト）と
  `databricks bundle validate -t dev`（バンドルの構文・参照チェック）を並行実行
- `main` への push 時のみ: 上記2つが通った後に `databricks bundle deploy -t dev --auto-approve` を実行して自動デプロイ

`deploy` ジョブは `test` と `validate` の両方に依存しているため、
ユニットテストが落ちていればデプロイは走りません。

> **`--auto-approve` について**: スキーマ / Volume の削除・再作成など破壊的な変更を
> 伴うデプロイは、対話的な承認プロンプトが出せない CI では既定だと失敗します。
> このバンドルはサンプル・学習用データのみを扱う前提で `--auto-approve` を付けており、
> 破壊的な変更（スキーマの削除・Volume の再作成など）も確認なしに自動実行されます。
> 本番相当のデータを扱うバンドルでは、この付け方を避けるか、
> デプロイ前に手動で `databricks bundle deploy` を実行してプランを確認する運用にしてください。

コンピュートは Actions の実行環境（GitHub 側）でのみ動くので、CI/CD 自体は
Databricks 側のサーバーレス枠をほとんど消費しません（実際にジョブやパイプラインを
実行するタイミングでのみワークスペース側のサーバーレスが使われます）。

### 1. サービスプリンシパル用のトークンを用意する

学習用途であればユーザー個人のパーソナルアクセストークンでも構いません。

1. Databricks の右上ユーザーメニュー → **Settings > Developer > Access tokens** を開く
2. **Generate new token** でトークンを発行し、値を控えます（一度しか表示されません）

### 2. GitHub リポジトリに Secrets を登録する

リポジトリの **Settings > Secrets and variables > Actions** で以下を登録します。

| Secret 名 | 値 |
| --- | --- |
| `DATABRICKS_HOST` | `https://dbc-b1c4d17f-58d9.cloud.databricks.com` |
| `DATABRICKS_TOKEN` | 手順1で発行したトークン |

### 3. 動作確認

`main` ブランチに何かしら変更を push すると、GitHub の **Actions** タブにワークフローが表示されます。

- `validate` ジョブが成功すればバンドル定義に問題なし
- `deploy` ジョブまで成功すれば、ワークスペースの `dev` ターゲットへ自動反映されます

Pull Request 上では `validate` のみが走り、デプロイは行われません。マージして `main` に
取り込まれたタイミングで初めて `deploy` が実行される、という一般的な CI/CD の流れです。

---

## 補足

- `mode: development` のため、デプロイされるリソース名には `[dev <ユーザー名>]` の接頭辞が付き、
  スケジュールは一時停止された状態になります。学習用途で他のユーザーと衝突しないための仕組みです。
- Free Edition ではサーバーレスコンピュートが自動的に使用されます。

## 開発時の注意点（過去に踏んだ落とし穴）

### UC のカタログ / スキーマ参照は必ず文字列リテラルで統一する

`mode: development` は、Job・Pipeline の**表示名**には `[dev <ユーザー名>]` を
先頭に付けるだけだが、`resources.schemas` / `resources.catalogs` として
バンドル管理した Unity Catalog スキーマ・カタログは、**物理名そのもの**を
`dev_<ユーザー名>_<name>` にリネームする。

この違いに気づかず、あるリソースは `schema: nyctaxi`（文字列リテラル）、
別のリソースは `schema_name: ${resources.schemas.nyctaxi_schema.name}`
（DAB 管理リソースの動的参照）という書き方を混在させたところ、
前者は `nyctaxi`、後者は `dev_recrpm33_nyctaxi` という**別のスキーマ**に
デプロイされてしまい、Auto Loader のパス (`/Volumes/workspace/nyctaxi/landing`)
が実体と一致しないバグを起こした。

**ルール**: 同じ UC オブジェクトを指すつもりの `catalog` / `schema` /
`catalog_name` / `schema_name` は、すべて文字列リテラルで書く
（`resources.schemas` / `resources.catalogs` の動的参照を使わない）。
このバンドルでは、Unity Catalog のスキーマはパイプラインの初回実行時に
自動作成される前提で、`resources/nyctaxi_pipeline.yml` と
`resources/nyctaxi_landing.yml` の両方で `catalog: workspace` /
`schema(_name): nyctaxi` を文字列リテラルとして揃えている。

この規約は `tests/test_resource_conventions.py` の
`test_schema_and_catalog_references_are_literal_strings` で機械的に
チェックしており、`resources/*.yml` のどこかで
`${resources.schemas...}` / `${resources.catalogs...}` を
catalog/schema 系フィールドの値に使うと CI の `test` ジョブが失敗する。
