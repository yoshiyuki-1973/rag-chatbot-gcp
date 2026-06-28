# 14 RAGデータ投入マニュアル

本書は、本システム（RAGチャットボット）に対して新規のスポーツルール等のドキュメント（Markdown / PDF）を追加・更新する手順を説明するマニュアルです。

---

## 1. データ投入（インジェスト）の全体フロー

本システムのデータ投入バッチは、以下の流れでテキストを処理してデータベースへ登録します。

```
[Markdown / PDF の配置]
         ↓
[sources.yaml にメタ情報を記述]
         ↓
[DB接続用 Proxy 等の起動] (GCP本番時のみ)
         ↓
[インジェストバッチの実行] (Docker)
   - テキスト抽出
   - 768次元ベクトル生成 (gemini-embedding-001)
   - DB登録 (documents / document_chunks)
         ↓
[ベクトル検索インデックスの再作成] (SQL)
```

---

## 2. 事前準備とディレクトリ構成

取り込むドキュメントファイルを、プロジェクトルートの `data/` 配下に格納します。

### ディレクトリ構成の例

```
rag-chatbot-gcp/
├── data/
│   ├── markdown/
│   │   └── soccer_rules.md      # Markdownファイルはこちら
│   └── pdf/
│       └── basketball_rules.pdf # PDFファイルはこちら
```

- **対応フォーマット**: Markdown (`.md`) または PDF (`.pdf`)
- **ファイル名**: 英語または日本語（半角英数字推奨）

---

## 3. データソースメタ情報（sources.yaml）の記述

バッチは `batch/sources.yaml` に定義されたファイルのみを処理します。ファイルを追加した際は、必ずこのYAMLファイルに設定を記述してください。

### スキーマと設定項目

```yaml
sources:
  - path: "data/markdown/soccer_rules.md"              # 必須: リポジトリルートからのファイルパス
    title: "サッカー競技規則 2023/24"                    # 必須: 出典名（UIに表示されます）
    source_url: "https://www.jfa.jp/laws/soccer/"      # 必須: 一次情報のURL（重複排除のキー）
    file_type: "markdown"                              # 必須: "markdown" または "pdf"
    organization: "JFA (日本サッカー協会)"               # 任意: 発行元組織名
    authority_score: 0.95                              # 必須: 信頼性スコア (0.00 〜 1.00)
    content_date: "2023-07-01"                         # 任意: ドキュメントの作成・更新日 (YYYY-MM-DD)
```

### 重要設定のルール

1. **`source_url` (重複排除キー)**:
   - この値はデータベース上で `UNIQUE` 制約となっています。
   - 同じ `source_url` を指定して再実行した場合、**既存の同一ドキュメントとそれに紐づくすべてのチャンクデータが削除され、新しい内容に上書き更新（upsert）**されます。
   - 完全に新しいドキュメントを追加したい場合は、必ず別のユニークな URL（またはダミーURL）を指定してください。
2. **`authority_score` (信頼性スコア)**:
   - UIの信頼性バッジ表示や、検索フィルタリングに使用されます。以下の目安で設定してください。
     - `0.90 〜 1.00`: FIFA、JOC、IOCなどの国際・国内公式統括団体
     - `0.70 〜 0.89`: 各競技の公式連盟・協会・ルールブック
     - `0.50 〜 0.69`: 大手スポーツメディア、報道機関
     - `0.30 〜 0.49`: Wikipediaや一般ブログ等

### 再投入時の挙動

現在のインジェストバッチは、ファイルの更新日時やハッシュによる差分検知は行いません。
`batch/sources.yaml` に記載されているデータソースを、実行のたびにすべて処理します。

| 操作 | 挙動 |
|---|---|
| PDF / Markdown を追加し、`sources.yaml` に追加する | 新しい `source_url` として `documents` に追加され、チャンクと Embedding が登録される |
| 既存ファイルの内容を変更し、同じ `source_url` のまま再実行する | `documents` のメタ情報を更新し、既存の `document_chunks` を全削除してから、新しいチャンクと Embedding を登録し直す |
| 変更していないファイルが `sources.yaml` に残っている | 変更していなくても再処理され、チャンクと Embedding が作り直される |
| `sources.yaml` から項目を削除する | 次回以降の処理対象から外れるだけで、DB 上の既存データは自動削除されない |
| 同じファイルで `source_url` を変更する | 別ドキュメントとして新規登録される。古い `source_url` のデータは自動削除されない |

> [!NOTE]
> 少量のデータでは全件再投入でも問題ありません。データ量が増えて API コストや実行時間が気になる場合は、将来的にファイルハッシュや `updated_at` を使った差分投入の仕組みを追加します。

---

## 4. インジェストバッチの実行手順

実行する環境（ローカル開発環境 or GCP本番/検証環境）に応じてコマンドを選択します。

### 4.1 ローカル開発環境への投入手順

1. **ローカルデータベース (PostgreSQL) が起動していることを確認**:
   ```powershell
   docker compose ps
   # db コンテナが「Up」であることを確認。起動していない場合は以下を実行
   # docker compose up -d db
   ```
2. **バッチ処理を実行する**:
   ```powershell
   docker compose run --rm --no-deps ingest
   ```
   *※環境変数 `DATABASE_URL` には、ローカルコンテナ内の DB (`db:5432`) が自動で設定されます。*

---

### 4.2 GCP環境（Staging / Production）への投入手順

GCP（Cloud SQL）への投入は、セキュリティの観点から **Cloud SQL Auth Proxy** を経由して安全に行います。

1. **対象の GCP プロジェクトを設定**:
   ```powershell
   # Stagingの場合
   gcloud config configurations activate rag-chatbot-stg

   # Productionの場合
   # gcloud config configurations activate rag-chatbot-prod
   ```
2. **Docker内でCloud SQL Auth Proxyを起動**:
   `host.docker.internal` はDocker Desktopの設定によって名前解決できないため、GCP投入では使用しません。`docker-compose.gcp.yml` のProxyをIngestと同じDockerネットワークで起動します。

   ```powershell
   docker info
   if ($LASTEXITCODE -ne 0) {
     throw "Docker Desktopを起動してください。"
   }

   # Stagingの場合
   $env:APP_ENV_FILE = ".env.stg"

   # Productionの場合
   # $env:APP_ENV_FILE = ".env.prod"

   $TERRAFORM_EXE = "C:\apps\terraform_1.15.7\terraform.exe"
   if (-not (Test-Path -LiteralPath $TERRAFORM_EXE)) {
     throw "Terraformが見つかりません: $TERRAFORM_EXE"
   }

   $CONNECTION_NAME_OUTPUT = & $TERRAFORM_EXE "-chdir=terraform" output -raw db_connection_name
   if ($LASTEXITCODE -ne 0) {
     throw "TerraformからCloud SQL接続名を取得できません。"
   }
   $env:CLOUD_SQL_CONNECTION_NAME = $CONNECTION_NAME_OUTPUT.Trim()

   if (-not (Test-Path -LiteralPath "$env:APPDATA\gcloud\application_default_credentials.json")) {
     throw "ADCが見つかりません。gcloud auth application-default loginを実行してください。"
   }

   docker compose -f docker-compose.yml -f docker-compose.gcp.yml up -d --force-recreate cloud-sql-proxy
   docker compose -f docker-compose.yml -f docker-compose.gcp.yml logs --tail 20 cloud-sql-proxy
   ```

   Proxyログに対象Cloud SQLインスタンスへの待受開始が表示されることを確認します。ProxyのポートはWindows側やLANへ公開されません。

3. **初回のみCloud SQLのスキーマを作成**:
   データ投入前に、Google Cloudコンソールの **Cloud SQL Studio** で `db/01_schema.sql` を実行します。

   1. 対象プロジェクトの **Cloud SQL** → 対象インスタンス → **Cloud SQL Studio**を開く。
   2. データベース `rag_chatbot`、ユーザー `app_user`、対象環境のDBパスワードで接続する。
   3. プロジェクトルートのPowerShellで次を実行し、スキーマSQLをクリップボードへコピーする。

      ```powershell
      Get-Content -LiteralPath ".\db\01_schema.sql" -Raw -Encoding UTF8 | Set-Clipboard
      ```

   4. Cloud SQL StudioのSQLエディタへ貼り付け、全SQLを実行する。
   5. 次のSQLを実行し、`documents`、`document_chunks`、`chat_history` の3行が表示されることを確認する。

      ```sql
      SELECT tablename
      FROM pg_tables
      WHERE schemaname = 'public'
        AND tablename IN ('documents', 'document_chunks', 'chat_history')
      ORDER BY tablename;
      ```

   > [!IMPORTANT]
   > `document_chunks` が存在しない状態では、データ投入もベクトル検索インデックスの再作成も実行できません。スキーマ作成は環境ごとに初回のみ必要です。

4. **環境別の環境変数ファイルを準備**:
   Stagingでは `.env.stg`、Productionでは `.env.prod` をプロジェクトルートに作成します。接続先にはComposeサービス名の `cloud-sql-proxy:5432` を指定します。`GCP_PROJECT_ID`には対象環境の実プロジェクトIDを設定してください。

   ```dotenv
   DATABASE_URL=postgresql://app_user:YOUR_DB_PASSWORD@cloud-sql-proxy:5432/rag_chatbot
   USE_VERTEX_AI=true
   GCP_PROJECT_ID=your-gcp-project-id
   GCP_LOCATION=asia-northeast1
   ```

   > [!IMPORTANT]
   > `.env.stg` または `.env.prod` に `host.docker.internal`、`localhost`、ホスト側の5433番ポートを指定しないでください。GCP投入時のDBホストは `cloud-sql-proxy`、ポートは `5432` です。

5. **バッチ処理を実行**:

   ```powershell
   docker compose -f docker-compose.yml -f docker-compose.gcp.yml build ingest

   docker compose -f docker-compose.yml -f docker-compose.gcp.yml run --rm --no-deps `
     -v "${env:APPDATA}/gcloud/application_default_credentials.json:/tmp/gcp-adc.json:ro" `
     -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcp-adc.json `
     ingest
   ```

   `data/` は `docker-compose.yml` によりIngestコンテナの `/app/data` へ読み取り専用でマウントされます。
   `batch/ingest.py` と `batch/sources.yaml` はイメージ内へコピーされるため、変更後は `build ingest` を省略しないでください。

   最初に `Database connection and required tables: OK`、最終行に `Completed: N/N files processed, 0 files failed` 相当が表示されることを確認します。現在の `batch/sources.yaml` では `Completed: 22/22 files processed, 0 files failed` が合格条件です。DB接続または必須テーブルの確認に失敗した場合は、Embedding生成前に処理が停止します。ファイルの失敗件数が1件以上の場合も終了コード1で停止します。

6. **Proxyを停止**:

   ```powershell
   docker compose -f docker-compose.yml -f docker-compose.gcp.yml stop cloud-sql-proxy
   Remove-Item Env:APP_ENV_FILE -ErrorAction SilentlyContinue
   Remove-Item Env:CLOUD_SQL_CONNECTION_NAME -ErrorAction SilentlyContinue
   ```

---

## 5. 投入後の動作検証とインデックス更新

### 5.0 登録件数の確認

Cloud SQL Studioで次のSQLを実行します。

```sql
SELECT
  (SELECT COUNT(*) FROM documents) AS documents,
  (SELECT COUNT(*) FROM document_chunks) AS chunks;
```

`documents` と `chunks` がともに1件以上であることを確認します。どちらかが0件の場合は、フロントエンドの動作確認やインデックス再構築へ進まず、§4.2のIngestを再確認してください。

### 5.1 ベクトル検索用インデックスの再構築 (必須)

インジェスト完了後、検索を高速化するためデータベース側でベクトル検索用インデックス（IVFFlat）を再ビルドします。
実行先がローカル DB か GCP Cloud SQL かによって、以下のいずれかの方法で SQL を実行します。

#### 方法A: ローカル Docker DB に対して Docker コマンドで実行する場合（推奨）

プロジェクトルートで、DB コンテナ内の `psql` を Docker 経由で実行します。ローカル PC に PostgreSQL クライアントをインストールする必要はありません。

```powershell
# DB コンテナが起動していることを確認
docker compose ps db

# インデックス再構築 SQL を実行
docker compose exec db psql -v ON_ERROR_STOP=1 -U postgres -d rag_chatbot -c "DROP INDEX IF EXISTS idx_document_chunks_embedding; CREATE INDEX idx_document_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);"
```

#### 方法B: ローカル PC の psql クライアントから実行する場合（任意）

Docker を使わず、ローカル PC にインストール済みの `psql` から実行したい場合のみ、この方法を使います。
通常のローカル開発では、方法Aの Docker コマンドで実行してください。

```powershell
# ローカル Docker DB に接続して SQL を実行
psql "postgresql://postgres:postgres_password@localhost:5432/rag_chatbot" -v ON_ERROR_STOP=1 -c "DROP INDEX IF EXISTS idx_document_chunks_embedding; CREATE INDEX idx_document_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);"
```

#### 方法C: Google CloudコンソールのCloud SQL Studioから実行する場合（推奨）

ローカルPCへ `psql` をインストールせず、Google Cloud上でインデックスを再作成できます。

1. [Google Cloudコンソール](https://console.cloud.google.com/)を開く。
2. 上部のプロジェクト選択欄で、対象プロジェクトを選択する。
   - Staging: Staging用プロジェクト
   - Production: Production用プロジェクト
3. **Cloud SQL** → 対象のPostgreSQLインスタンスを開く。
   - Staging: `rag-db-stg`
   - Production: `rag-db-prod`
4. **Cloud SQL Studio**を開く。
5. 次の接続情報を入力して接続する。
   - データベース: `rag_chatbot`
   - ユーザー: `app_user`
   - パスワード: 対象環境のtfvarsで設定したDBパスワード
6. 次のSQLを実行し、`document_chunks` が存在することを確認する。

```sql
SELECT to_regclass('public.document_chunks') AS table_name;
```

`table_name` が `document_chunks` ではなく `NULL` の場合は、インデックスを操作せず、§4.2の手順3で `db/01_schema.sql` を実行します。

7. SQLエディタへ次のSQLを貼り付け、実行する。

```sql
DROP INDEX IF EXISTS idx_document_chunks_embedding;

CREATE INDEX idx_document_chunks_embedding
ON document_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 10);
```

8. 次のSQLを実行し、`idx_document_chunks_embedding` が表示されることを確認する。

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'document_chunks'
  AND indexname = 'idx_document_chunks_embedding';
```

> [!CAUTION]
> Productionでインデックスを再作成すると、対象テーブルへの処理に影響する可能性があります。利用の少ない時間帯に実行し、完了するまで画面を閉じないでください。

#### 方法D: GCP Cloud SQL Auth Proxy 経由で psql から実行する場合

Cloud SQL Studio を使わず、ローカル端末から Cloud SQL に接続する場合の手順です。

```powershell
# 1. 対象環境を選択
gcloud config configurations activate rag-chatbot-prod

# 2. 別ターミナルで Cloud SQL Auth Proxy を起動
$CONNECTION_NAME = terraform "-chdir=terraform" output -raw db_connection_name
$CLOUD_SQL_PROXY_EXE = "C:\apps\cloud-sql-proxy\cloud-sql-proxy.exe"
& $CLOUD_SQL_PROXY_EXE --port 5433 $CONNECTION_NAME

# 3. 元のターミナルで Cloud SQL に接続して SQL を実行
psql "postgresql://app_user:YOUR_DB_PASSWORD@localhost:5433/rag_chatbot" -v ON_ERROR_STOP=1 -c "DROP INDEX IF EXISTS idx_document_chunks_embedding; CREATE INDEX idx_document_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);"
```

実行する SQL は以下です。

```sql
-- 既存のインデックスがある場合は一度削除
DROP INDEX IF EXISTS idx_document_chunks_embedding;

-- インデックスの新規作成
-- lists は sqrt(チャンク総数) 程度が推奨 (例: 1000チャンクなら 32, 100チャンク以下なら 10)
CREATE INDEX idx_document_chunks_embedding
ON document_chunks USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 10);
```

作成状況を確認する場合は、接続先 DB で以下を実行します。

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'document_chunks'
  AND indexname = 'idx_document_chunks_embedding';
```

### 5.2 ログの確認

バッチ実行時にコンソールに出力されるログを確認し、エラーがないことを確認します。
```
[INFO] Processing: data/markdown/soccer_rules.md
[INFO]   Extracted 8540 chars
[INFO]   Created 18 chunks
[INFO]   Generated embeddings
[INFO]   Upserted document: https://www.jfa.jp/laws/soccer/ (id: e3bd9d...)
[INFO]   Inserted 18 chunks
[INFO] Completed: 1/1 files processed, 0 files failed
```

---

## 6. トラブルシューティング

### Q1. インジェスト実行時に API エラーが発生する
- **原因**: Vertex AI の API が有効化されていない、または IAM 認証情報（ADC）が不足しています。
- **対処**: 
  - 本番/検証環境の場合は、事前に `gcloud auth application-default login` を実行したか確認してください。
  - ローカル開発環境の場合は、`.env` に `GEMINI_API_KEY` が正しく記述され、`USE_VERTEX_AI=false` になっているか確認してください。

### Q2. 登録したドキュメントを完全に削除したい
- メタ情報定義の変更等で一旦削除したい場合は、データベース上で直接 `DELETE` 文を実行します。外部キーが `CASCADE` 設定されているため、紐づくチャンクも自動で全削除されます。
  ```sql
  -- 特定ドキュメントの削除 (source_url を指定)
  DELETE FROM documents WHERE source_url = 'https://www.jfa.jp/laws/soccer/';
  ```

### Q3. `relation "document_chunks" does not exist` が表示される

- **原因**: 対象環境の `rag_chatbot` データベースで初回スキーマを作成していないか、別のデータベースへ接続しています。
- **対処**:
  1. Cloud SQL Studioで `SELECT current_database();` を実行し、`rag_chatbot` であることを確認する。
  2. §4.2の手順3に従い、`db/01_schema.sql` 全体を実行する。
  3. `documents`、`document_chunks`、`chat_history` の存在を確認してからデータ投入・インデックス再構築を行う。

### Q4. Docker APIまたは`dockerDesktopLinuxEngine`へ接続できない

- **原因**: Docker Desktopが起動していません。
- **対処**: Docker Desktopを起動し、`docker info` が成功してから再実行します。

### Q5. GCP投入時に`pgvector/pgvector`を起動しようとする

- **原因**: GCP用Composeファイルまたは `--no-deps` の指定がなく、ローカルDBも依存サービスとして起動しようとしています。
- **対処**: `docker compose -f docker-compose.yml -f docker-compose.gcp.yml run --rm --no-deps ingest` を使用します。

### Q6. `sed`または`cloud-sql-proxy`が見つからない

- **原因**: Linux用の古いコマンド例をPowerShellで実行しているか、Cloud SQL Auth Proxyが未インストールです。
- **対処**: GCP Ingestでは§4.2のDocker内Proxy方式を使用するため、Windows版Proxyの実行ファイルは不要です。ローカルの`psql`から接続する方法Dを使用する場合だけ、Windows版Proxyをインストールします。

### Q7. 画面に「ベクトル検索に失敗しました」と表示される

- **原因**: スキーマ未作成、RAGデータ未投入、またはEmbedding・DB検索処理のエラーです。
- **対処**:
  1. Cloud Runのバックエンドログを確認する。
  2. `UndefinedTableError: relation "document_chunks" does not exist` があれば、§4.2の手順3でスキーマを作成する。
  3. テーブルが存在する場合は§5.0で件数を確認し、0件ならIngestを実行する。
  4. 件数がある場合は、Vertex AIの権限、Embeddingの次元、Cloud Runログの直前の例外を確認する。

> [!NOTE]
> バックエンドの `/health` が正常でも、現行実装はDB接続確認のみで、必須テーブルの存在や投入件数までは検査しません。

### Q8. 全ファイルが`[Errno -2] Name or service not known`で失敗する

- **原因**: `.env.stg`または`.env.prod`のDBホストに `host.docker.internal` が設定され、Ingestコンテナから名前解決できていません。
- **対処**:
  1. `DATABASE_URL`のホストとポートを `cloud-sql-proxy:5432` に変更する。
  2. §4.2の手順2でDocker内Proxyを起動する。
  3. Proxyログを確認してからIngestを再実行する。

このエラーでは、PDF抽出・チャンク分割・Embedding生成が成功していてもDBへは1件も保存されません。修正版のIngestはDB接続を最初に確認するため、同じ状態ではEmbedding生成前に停止します。
