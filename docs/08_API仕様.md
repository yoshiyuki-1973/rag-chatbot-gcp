# 08 API 仕様

ベース URL:
- 開発: `http://localhost:8000`
- 本番: `https://<app-name>.onrender.com`

---

## 1. POST /chat

ユーザーの質問に対してRAGで回答を生成し、出典付きで返す。

### リクエスト

```http
POST /chat
Content-Type: application/json
```

```json
{
  "query": "サッカーのオフサイドルールを教えてください",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "top_k": 5
}
```

| フィールド | 型 | 必須 | デフォルト | 説明 |
|---|---|---|---|---|
| query | string | 必須 | — | ユーザーの質問文（1〜500文字） |
| session_id | string | 任意 | null | セッション識別子（UUIDv4推奨）。会話履歴保存に使用 |
| top_k | integer | 任意 | 5 | 取得する類似チャンク数（1〜20） |

### レスポンス（200 OK）

```json
{
  "answer": "オフサイドとは、攻撃側の選手がボールよりも相手ゴール側に位置し...",
  "sources": [
    {
      "document_id": "550e8400-e29b-41d4-a716-446655440001",
      "title": "FIFA サッカー競技規則 2024/25",
      "source_url": "https://www.fifa.com/football-rules/",
      "organization": "FIFA",
      "authority_score": 0.95,
      "chunk_index": 12,
      "similarity": 0.87
    },
    {
      "document_id": "550e8400-e29b-41d4-a716-446655440002",
      "title": "JFA サッカー解説",
      "source_url": "https://www.jfa.jp/",
      "organization": "JFA",
      "authority_score": 0.85,
      "chunk_index": 3,
      "similarity": 0.82
    }
  ],
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| フィールド | 型 | 説明 |
|---|---|---|
| answer | string | LLM が生成した回答テキスト |
| sources | array | 参照した出典情報の配列（similarity 降順） |
| sources[].document_id | string (UUID) | ドキュメントの ID |
| sources[].title | string | ドキュメントタイトル |
| sources[].source_url | string | 元ドキュメントの URL |
| sources[].organization | string \| null | 発行元組織名 |
| sources[].authority_score | number | 信頼性スコア（0〜1） |
| sources[].chunk_index | integer | チャンク番号（0始まり） |
| sources[].similarity | number | コサイン類似度（0〜1） |
| session_id | string \| null | セッション識別子 |

### エラーレスポンス

| ステータス | コード | 説明 |
|---|---|---|
| 422 | VALIDATION_ERROR | リクエストボディの形式が不正（空クエリ・文字数超過・top_k範囲外など Pydantic バリデーション失敗） |
| 500 | LLM_ERROR | LLM API の呼び出しに失敗 |
| 500 | SEARCH_ERROR | ベクトル検索に失敗 |
| 503 | LLM_UNAVAILABLE | LLM サービスが利用不可 |

```json
{
  "detail": {
    "code": "LLM_ERROR",
    "message": "LLM サービスへの接続に失敗しました。しばらく後にお試しください。"
  }
}
```

---

## 2. POST /search

ベクトル類似検索のみを行い、LLM を呼ばずに関連チャンクを返す（デバッグ・評価用）。

### リクエスト

```http
POST /search
Content-Type: application/json
```

```json
{
  "query": "オフサイド",
  "top_k": 5,
  "min_similarity": 0.5,
  "min_authority_score": 0.0
}
```

| フィールド | 型 | 必須 | デフォルト | 説明 |
|---|---|---|---|---|
| query | string | 必須 | — | 検索クエリ |
| top_k | integer | 任意 | 5 | 取得件数（1〜20） |
| min_similarity | number | 任意 | 0.0 | 類似度の下限フィルター（0〜1） |
| min_authority_score | number | 任意 | 0.0 | 信頼性スコアの下限フィルター（0〜1） |

### レスポンス（200 OK）

```json
{
  "results": [
    {
      "document_id": "550e8400-e29b-41d4-a716-446655440001",
      "chunk_index": 12,
      "content": "第11条 オフサイド\n選手がオフサイドの位置にいることは...",
      "similarity": 0.87,
      "title": "FIFA サッカー競技規則 2024/25",
      "source_url": "https://www.fifa.com/football-rules/",
      "organization": "FIFA",
      "authority_score": 0.95
    }
  ],
  "total": 1
}
```

---

## 3. GET /health

API サーバーと各依存サービスの死活確認。

### リクエスト

```http
GET /health
```

### レスポンス（200 OK）

```json
{
  "status": "ok",
  "version": "0.1.0",
  "services": {
    "database": "ok",
    "llm": "ok"
  }
}
```

| `services[*]` の値 | 意味 |
|---|---|
| `"ok"` | 接続・疎通確認成功 |
| `"degraded"` | レスポンスはあるが遅延や一部エラーあり |
| `"error"` | 接続失敗 |

サービスのいずれかが `"error"` の場合、HTTP 503 を返す。

---

## 4. 共通仕様

### 4.1 認証

MVP では認証なし（ポートフォリオ公開用途のためレート制限のみ検討）。

将来的には Bearer Token（JWT）認証を追加する。

### 4.2 CORS 設定

Next.js フロントエンドのオリジンのみ許可。

```python
origins = [
    "https://<project-name>.vercel.app",
    "http://localhost:3000",  # 開発環境
]
```

### 4.3 レート制限（将来）

Render Free Tier での過負荷防止のため、slowapi を使い `/chat` は 10 req/min/IP を目安に制限する。

### 4.4 エラーフォーマット

FastAPI デフォルトの形式に統一する。

```json
{
  "detail": "エラーの詳細メッセージ（日本語）"
}
```

または構造化エラーの場合:

```json
{
  "detail": {
    "code": "ERROR_CODE",
    "message": "ユーザー向けの日本語メッセージ"
  }
}
```

### 4.5 ログ形式

```json
{
  "timestamp": "2026-04-25T10:00:00Z",
  "level": "INFO",
  "endpoint": "/chat",
  "query_length": 20,
  "retrieved_chunks": 5,
  "llm_latency_ms": 1230,
  "total_latency_ms": 1450
}
```

スタックトレースはログのみに出力し、レスポンスには含めない。



