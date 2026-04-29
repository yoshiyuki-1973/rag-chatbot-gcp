# 06 RAG設計・LLM設計・バッチ処理設計

## 1. RAG 設計

### 1.1 チャンク分割方針

#### 基本パラメータ

| パラメータ | 値 | 理由 |
|---|---|---|
| chunk_size | 500 トークン | LLM のコンテキスト上限（Gemini: 128K）に対して余裕を持ちつつ、1 チャンクに意味のある情報量を確保 |
| chunk_overlap | 50 トークン | チャンク境界で文脈が切れるのを防ぐ。10% 程度のオーバーラップが一般的 |
| splitter | 独自 chunker | 段落 → 文 → 文字の順に分割し、意味の切れ目でチャンクを分割する |

#### 分割の優先順位（独自 chunker のセパレータ）

```python
separators = ["\n\n", "\n", "。", ".", " ", ""]
```

段落区切り（`\n\n`）を最優先にすることで、段落単位の意味的まとまりを維持する。

#### Markdown 固有の処理

- 見出し（`#`〜`######`）をチャンクのメタ情報として保持する（将来の section-aware 検索に対応）
- コードブロック（` ``` ` ）はそのまま 1 チャンクに収める（分割すると文脈が失われるため）
- テーブルは可能な限り分割しない

#### PDF 固有の処理

- PyMuPDF（fitz）でテキスト抽出する
- ページ番号をメタ情報として保持し、出典表示に使用できるようにする
- 図・表のキャプションはテキストとして取得できる場合のみ取り込む

---

### 1.2 Embedding 生成方針

| 項目 | 選択 | 理由 |
|---|---|---|
| モデル | `text-embedding-3-small`（OpenAI） | 1536 次元・低コスト・日本語対応 |
| 次元数 | 1536 | Supabase pgvector VECTOR(1536) に対応 |
| バッチサイズ | 100 チャンクずつ | API レート制限に対応しつつ効率的に処理 |
| エラー時の挙動 | リトライ 3 回後スキップ・ログ出力 | 一部失敗しても全体を止めない |

> **補足**: Gemini が Embeddings API を提供する場合は Gemini に切り替えることでコストを統一できる。OpenAI Embeddings は低コスト（$0.02/1M tokens）のため現状維持でも問題ない。

---

### 1.3 類似検索の方法

#### 検索クエリのベクトル化

```python
query_embedding = embed(user_query)  # text-embedding-3-small
```

#### pgvector でのコサイン類似度検索

```sql
SELECT
    c.id,
    c.document_id,
    c.chunk_index,
    c.content,
    1 - (c.embedding <=> $1) AS similarity,
    d.title,
    d.source_url,
    d.organization,
    d.authority_score
FROM document_chunks c
JOIN documents d ON c.document_id = d.id
WHERE c.embedding IS NOT NULL
ORDER BY c.embedding <=> $1  -- コサイン距離（小さいほど類似）
LIMIT $2;  -- top-k (デフォルト: 5)
```

- 演算子 `<=>` はコサイン距離（0 が完全一致、2 が逆方向）
- `1 - distance` で類似度（0〜1）に変換してレスポンスに含める

#### フィルタリング（オプション）

- `authority_score >= 0.5` などで低信頼ソースを除外できる
- MVP では全件検索し、フロントで表示の強調を変える

---

### 1.4 プロンプト設計

#### システムプロンプト

```
あなたはスポーツに関する質問に答えるアシスタントです。
以下のルールに従ってください。

1. 必ず提供されたコンテキストの情報のみを使用して回答してください。
2. コンテキストに情報がない場合は「提供された情報の中には該当する情報が見つかりませんでした」と回答してください。
3. 回答は日本語で行ってください。
4. 推測や創作は行わないでください。
5. 回答の根拠となったドキュメントは別途出典として提示されます。

コンテキスト:
{context}
```

#### コンテキストの組み立て

```python
context = "\n\n---\n\n".join([
    f"[出典: {chunk['title']}]\n{chunk['content']}"
    for chunk in retrieved_chunks
])
```

- 各チャンクの先頭に出典タイトルを付与することで、LLM が情報の出所を把握できるようにする
- チャンク間は区切り線で分離し、LLM が境界を認識しやすくする

#### ユーザーターン

```
{user_query}
```

---

## 2. LLM 設計

### 2.1 LLM 抽象層

LLM の差し替えを可能にするため、抽象基底クラス `BaseLLMClient` を定義し、具体実装を差し替える。

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator

class BaseLLMClient(ABC):
    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1000,
        temperature: float = 0.1,
    ) -> str:
        """単一の回答テキストを返す"""
        ...

    async def stream(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1000,
        temperature: float = 0.1,
    ) -> AsyncIterator[str]:
        """デフォルトでは generate の結果を 1 回だけ返す"""
        yield await self.generate(system_prompt, user_message, max_tokens, temperature)
```

#### 現在の実装: GeminiLLMClient

```python
class GeminiLLMClient(BaseLLMClient):
    """Google Gen AI SDK を使って Gemini API に接続する実装"""

    def __init__(self, api_key: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        self.model = model

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1000,
        temperature: float = 0.1,
    ) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""
```

#### 将来の差し替え例

| LLM | 実装クラス | 変更箇所 |
|---|---|---|
| Claude（Anthropic） | `ClaudeLLMClient` | `anthropic.AsyncAnthropic` を使用。`system` パラメータが別途必要 |
| OpenAI GPT-4o | `OpenAILLMClient` | OpenAI SDK を使用する Adapter を追加する |
| ローカル LLM（Ollama） | `OllamaLLMClient` | `base_url` を `http://localhost:11434/v1` に変更 |

### 2.2 初期化と注入パターン

LLM は起動時に `main.py` の `_create_llm_client(settings)` ファクトリで生成し、`app.state.llm` に格納する。ルーターは `dependencies.py` の `get_rag_service()` 経由で `app.state.llm` を受け取る。

```python
# main.py
def _create_llm_client(settings: Settings) -> BaseLLMClient:
    """LLM_PROVIDER に基づいてクライアントを生成するファクトリ。
    新規プロバイダー追加時はここに elif を足し、対応 Adapter を実装する。"""
    if settings.llm_provider == "gemini":
        return GeminiLLMClient(settings.gemini_api_key, settings.gemini_model)
    raise RuntimeError(f"Unsupported LLM_PROVIDER: {settings.llm_provider!r}")

# dependencies.py
def get_rag_service(request: Request) -> RAGService:
    return RAGService(
        embedder=request.app.state.embedder,
        vector_store=SupabaseVectorStore(request.app.state.db_pool),
        llm=request.app.state.llm,  # app.state 経由で注入
    )
```

MVP では `LLM_PROVIDER=gemini` のみ実装し、Claude・OpenAI は Adapter 追加時に切り替え対象へ加える。

### 2.3 temperature の設計方針

- **temperature: 0.1** を基本とする
- RAG では「コンテキストに基づいた正確な回答」が目的であり、創造性より正確性を優先するため低温度に設定する
- 自由な文章生成が必要な場合（要約等）は 0.3〜0.5 に上げることを検討する

---

## 3. バッチ処理設計（Ingest Pipeline）

### 3.1 全体フロー

```
data/
├── markdown/
│   └── *.md
└── pdf/
    └── *.pdf

↓ ingest.py 実行

1. sources.yaml を読み込む（メタ情報・authority_score）
2. ファイルを列挙する
3. 各ファイルを処理する
   3a. テキスト抽出
   3b. チャンク分割
   3c. Embedding 生成（バッチ）
   3d. DB upsert（documents）
   3e. DB insert（document_chunks）
4. 処理サマリーをログ出力する
```

### 3.2 sources.yaml の構造

```yaml
sources:
  - path: data/markdown/joc_overview.md
    title: JOC 概要
    source_url: https://www.joc.or.jp/about/
    organization: JOC
    authority_score: 0.90
    content_date: 2024-01-01
    file_type: markdown

  - path: data/pdf/fifa_report_2022.pdf
    title: FIFA ワールドカップ 2022 技術レポート
    source_url: https://digitalhub.fifa.com/
    organization: FIFA
    authority_score: 0.95
    content_date: 2023-06-01
    file_type: pdf
```

### 3.3 テキスト抽出

#### Markdown

Markdown は見出し・表・コードブロックの文脈を保持するため、生テキストのまま取り込む。

```python
from pathlib import Path

def extract_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")
```

#### PDF

```python
import fitz  # PyMuPDF

def extract_pdf(path: str) -> str:
    doc = fitz.open(path)
    pages = [page.get_text() for page in doc]
    return "\n\n".join(pages)
```

### 3.4 チャンク分割

独自 chunker で段落区切り（`\n\n`）を優先し、長い段落は文末記号（`。.!?`）で分割する。境界部分は token 数ベースで overlap を保持する。

### 3.5 Embedding 生成（バッチ）

```python
from openai import OpenAI

client = OpenAI(api_key=settings.OPENAI_API_KEY)
BATCH_SIZE = 100

def embed_chunks(chunks: list[str]) -> list[list[float]]:
    embeddings = []
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=batch,
        )
        embeddings.extend([e.embedding for e in response.data])
    return embeddings
```

### 3.6 DB 登録（冪等性の担保）

```python
def upsert_document(conn, meta: dict) -> str:
    """source_url が既存なら UPDATE、なければ INSERT し、document_id を返す"""
    result = conn.execute(
        """
        INSERT INTO documents (title, source_url, file_type, organization, authority_score, content_date)
        VALUES (%(title)s, %(source_url)s, %(file_type)s, %(organization)s, %(authority_score)s, %(content_date)s)
        ON CONFLICT (source_url) DO UPDATE
            SET title = EXCLUDED.title,
                organization = EXCLUDED.organization,
                authority_score = EXCLUDED.authority_score,
                content_date = EXCLUDED.content_date,
                updated_at = now()
        RETURNING id
        """,
        meta,
    )
    return result.fetchone()["id"]

def insert_chunks(conn, document_id: str, chunks: list[str], embeddings: list):
    """既存チャンクを削除してから再 insert（再取り込み対応）"""
    conn.execute("DELETE FROM document_chunks WHERE document_id = %s", (document_id,))
    conn.executemany(
        """
        INSERT INTO document_chunks (document_id, chunk_index, content, embedding, token_count)
        VALUES (%s, %s, %s, %s, %s)
        """,
        [
            (document_id, i, chunk, embedding, len(chunk.split()))
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ],
    )
```

### 3.7 Docker 設定

```dockerfile
# batch/Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "ingest.py"]
```

```yaml
# docker-compose.yml（バッチ用）
services:
  ingest:
    build:
      context: ./batch
    env_file: .env
    volumes:
      - ./data:/app/data:ro
    command: python ingest.py --sources sources.yaml
```

実行コマンド:

```bash
docker compose run --rm ingest
```



