# 16 RAG データ投入マニュアル

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
   - 768次元ベクトル生成 (text-embedding-004)
   - DB登録 (documents / document_chunks)
         ↓
[ベクトル検索インデックスの再作成] (SQL)
```

---

## 2. 事前準備とディレクトリ構成

取り込むドキュメントファイルを、プロジェクトルートの `data/` 配下に格納します。

### ディレクトリ構成の例

```
rag-chatbot/
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

---

## 4. インジェストバッチの実行手順

実行する環境（ローカル開発環境 or GCP本番/検証環境）に応じてコマンドを選択します。

### 4.1 ローカル開発環境への投入手順

1. **ローカルデータベース (PostgreSQL) が起動していることを確認**:
   ```bash
   docker compose ps
   # db コンテナが「Up」であることを確認。起動していない場合は以下を実行
   # docker compose up -d db
   ```
2. **バッチ処理を実行する**:
   ```bash
   docker compose run --rm ingest
   ```
   *※環境変数 `DATABASE_URL` には、ローカルコンテナ内の DB (`db:5432`) が自動で設定されます。*

---

### 4.2 GCP環境（Staging / Production）への投入手順

GCP（Cloud SQL）への投入は、セキュリティの観点から **Cloud SQL Auth Proxy** を経由して安全に行います。

1. **対象の GCP プロジェクトを設定**:
   ```bash
   # 例: 検証環境 (stg) の場合
   gcloud config set project rag-chatbot-stg
   
   # 例: 本番環境 (prod) の場合
   gcloud config set project rag-chatbot-prod
   ```
2. **Cloud SQL Auth Proxy の起動**:
   ローカルマシンの 5432 ポートを Cloud SQL の 5432 に接続します。
   ```bash
   # ローカルで起動中のDBがあれば事前に停止しておく必要があります
   # docker compose down
   
   # Proxy を起動 (ポート 5432)
   cloud-sql-proxy --port 5432 $(gcloud config get-value project):asia-northeast1:rag-db-$(gcloud config get-value project | sed 's/.*-//')
   ```
3. **本番用環境変数ファイル `.env.prod` の準備**:
   データベース接続先が Proxy（`localhost:5432`）に向いており、`USE_VERTEX_AI=true` になっていることを確認します。
   ```
   DATABASE_URL=postgresql://app_user:YOUR_DB_PASSWORD@localhost:5432/rag_chatbot
   USE_VERTEX_AI=true
   GCP_PROJECT_ID=your-gcp-project-id
   GCP_LOCATION=asia-northeast1
   ```
4. **バッチ処理を実行**:
   ```bash
   docker compose --env-file .env.prod run --rm ingest
   ```

---

## 5. 投入後の動作検証とインデックス更新

### 5.1 ベクトル検索用インデックスの再構築 (必須)

インジェスト完了後、検索を高速化するためデータベース側でベクトル検索用インデックス（IVFFlat）を再ビルドします。
GCPコンソールの Cloud SQL Studio や、ローカルの `psql` クライアントから接続し、以下の SQL を実行します。

```sql
-- 既存のインデックスがある場合は一度削除
DROP INDEX IF EXISTS idx_document_chunks_embedding;

-- インデックスの新規作成
-- lists は sqrt(チャンク総数) 程度が推奨 (例: 1000チャンクなら 32, 100チャンク以下なら 10)
CREATE INDEX idx_document_chunks_embedding
ON document_chunks USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 10);
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
