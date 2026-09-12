# databricks-dab-practice

Databricks Asset Bundles (DAB) の学習用プロジェクトです。
Hello World を出力する Notebook と Job、および NYC タクシーデータのメダリオンパイプラインを DAB で管理します。

## 構成

```
.
├── databricks.yml                  # バンドル定義（バンドル名 / ターゲット）
├── resources/
│   ├── hello_world_job.yml         # Job 定義（Notebook を実行）
│   ├── nyctaxi_landing.yml         # ランディング用 Volume 定義
│   ├── nyctaxi_pipeline.yml        # パイプライン定義（メダリオン構成）
│   ├── nyctaxi_job.yml             # Job 定義（パイプラインを起動）
│   └── nyctaxi_seed_job.yml        # Job 定義（CSV をランディングゾーンへ投入）
├── notebooks/
│   ├── hello_world.py              # Hello World を出力する Notebook
│   └── seed_nyctaxi_csv.py         # CSV シード投入用 Notebook
├── pipelines/
│   ├── nyctaxi_pipeline.py         # bronze(Auto Loader) / silver / gold を宣言する Python（dlt 依存）
│   └── transforms.py               # 変換ロジック本体（純粋関数、pytest でテスト可能）
├── tests/
│   ├── conftest.py                 # ローカル SparkSession フィクスチャ
│   └── test_transforms.py          # transforms.py のユニットテスト
└── requirements-test.txt           # テスト用依存関係（pyspark, pytest）
```

- Job: `hello_world_job` — タスク `hello_world_task` が `notebooks/hello_world.py` を実行
- Pipeline: `nyctaxi_pipeline` — Lakeflow Declarative Pipelines（旧 Delta Live Tables）
- Job: `nyctaxi_job` — `pipeline_task` で上記パイプラインを起動（毎日 6:00 JST）
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

`nyctaxi_job` は `pipeline_task` でパイプライン ID を参照しており、
ID はバンドルのデプロイ時に `${resources.pipelines.nyctaxi_pipeline.id}` で自動解決されます。
スケジュール（毎日 6:00 JST）を設定していますが、`mode: development` のターゲットでは
自動的に一時停止された状態でデプロイされます。

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
Bundle エディタが開きます。左側にバンドルのリソース（`hello_world_job`）が表示されます。

### 3. ターゲットを選んでデプロイする

1. エディタ右上のターゲット選択で **dev** を選びます。
2. **Deploy** をクリックします。
3. デプロイログが表示され、完了すると `[dev <ユーザー名>] hello_world_job` が作成されます。

### 4. Job を実行する

1. リソース一覧から `hello_world_job` を選び、**Run** をクリックします。
2. 実行結果のセル出力に `Hello World` が表示されます。
3. **ジョブとパイプライン** 画面からも実行履歴を確認できます。

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
`[dev <your-name>] hello_world_job` という名前の Job が作成されます。

### 7. Job を実行する

```bash
databricks bundle run hello_world_job -t dev
```

実行ログに `Hello World` が出力されます。
Databricks 画面の **ジョブとパイプライン** からも実行・結果確認ができます。

### 8. 後片付け（任意）

```bash
databricks bundle destroy -t dev
```

デプロイした Job とファイルが削除されます。

## C. GitHub Actions から自動デプロイする（CI/CD）

`.github/workflows/deploy.yml` に、以下を行う GitHub Actions ワークフローを用意しています。

- Pull Request 作成時・`main` への push 時: `pytest tests/`（ユニットテスト）と
  `databricks bundle validate -t dev`（バンドルの構文・参照チェック）を並行実行
- `main` への push 時のみ: 上記2つが通った後に `databricks bundle deploy -t dev` を実行して自動デプロイ

`deploy` ジョブは `test` と `validate` の両方に依存しているため、
ユニットテストが落ちていればデプロイは走りません。

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
