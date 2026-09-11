# databricks-dab-practice

Databricks Asset Bundles (DAB) の学習用プロジェクトです。
Hello World を出力する Notebook と Job、および NYC タクシーデータのメダリオンパイプラインを DAB で管理します。

## 構成

```
.
├── databricks.yml                  # バンドル定義（バンドル名 / ターゲット）
├── resources/
│   ├── hello_world_job.yml         # Job 定義（Notebook を実行）
│   └── nyctaxi_pipeline.yml        # パイプライン定義（メダリオン構成）
├── notebooks/
│   └── hello_world.py              # Hello World を出力する Notebook
└── pipelines/
    └── nyctaxi_pipeline.py         # bronze / silver / gold を宣言する Python
```

- Job: `hello_world_job` — タスク `hello_world_task` が `notebooks/hello_world.py` を実行
- Pipeline: `nyctaxi_pipeline` — Lakeflow Declarative Pipelines（旧 Delta Live Tables）
- Free Edition はサーバーレスコンピュートのみ利用できるため、クラスタ定義は含めていません

## データパイプライン（nyctaxi_pipeline）

Databricks に最初から用意されているサンプル `samples.nyctaxi.trips` を入力に、
メダリオンアーキテクチャの3層を宣言的に定義しています。

| レイヤ | テーブル | 内容 |
| --- | --- | --- |
| Bronze | `trips_bronze` | サンプルデータをそのまま取り込み |
| Silver | `trips_silver` | 品質チェック（運賃・距離・時刻）で不正行を除外し、乗車時間と距離あたり運賃を付与 |
| Gold | `trips_daily_gold` | 乗車日 × 乗車 ZIP ごとの件数・平均運賃・平均距離を集計 |

- 出力先は `workspace.nyctaxi` スキーマ（`resources/nyctaxi_pipeline.yml` の `catalog` / `schema`）
- 品質ルールは `@dlt.expect_all_or_drop` で定義。違反行は取り込まれず、パイプライン画面でドロップ件数を確認できます

### 実行方法

デプロイ後、Bundle resources から `nyctaxi_pipeline` を選んで **Run** すると全レイヤが更新されます。
CLI の場合は以下です。

```bash
databricks bundle run nyctaxi_pipeline -t dev
```

実行後、カタログエクスプローラの `workspace > nyctaxi` に3つのテーブルが作成されます。
SQL エディタから確認できます。

```sql
SELECT * FROM workspace.nyctaxi.trips_daily_gold ORDER BY trip_count DESC LIMIT 20;
```

## デプロイ方法は2通り

- **A. ワークスペース UI（Bundle エディタ）からデプロイ** — ローカルに何もインストール不要。おすすめ
- **B. ローカル PC の Databricks CLI からデプロイ** — CI/CD や本番運用向け

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

## 補足

- `mode: development` のため、デプロイされるリソース名には `[dev <ユーザー名>]` の接頭辞が付き、
  スケジュールは一時停止された状態になります。学習用途で他のユーザーと衝突しないための仕組みです。
- Free Edition ではサーバーレスコンピュートが自動的に使用されます。
