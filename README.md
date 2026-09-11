# databricks-dab-practice

Databricks Asset Bundles (DAB) の学習用プロジェクトです。
Hello World を出力する Notebook を 1 つ用意し、それを実行する Job を 1 つ DAB で管理します。

## 構成

```
.
├── databricks.yml              # バンドル定義（バンドル名 / ターゲット）
├── jobs/
│   └── hello_world_job.yml     # Job 定義（Notebook を実行）
└── notebooks/
    └── hello_world.py          # Hello World を出力する Notebook
```

- Notebook: `notebooks/hello_world.py`（Databricks Notebook 形式の Python ファイル）
- Job: `hello_world_job` — タスク `hello_world_task` が上記 Notebook を実行
- Free Edition はサーバーレスコンピュートのみ利用できるため、Job にクラスタ定義は含めていません

## Databricks Free Edition へのデプロイ手順

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
databricks auth login --host https://<your-workspace>.cloud.databricks.com
```

ブラウザが開くので OAuth でログインします。プロファイル名を聞かれたら任意の名前
（例: `free-edition`）を入力します。設定は `~/.databrickscfg` に保存されます。

### 4. ワークスペース URL を設定する

`databricks.yml` の `targets.dev.workspace.host` を、手順 1 で控えた自分のワークスペース URL に書き換えます。

```yaml
targets:
  dev:
    workspace:
      host: https://dbc-xxxxxxxx-xxxx.cloud.databricks.com
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
