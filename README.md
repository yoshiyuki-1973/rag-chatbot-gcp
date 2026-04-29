# スポーツルールRAGチャットボット

スポーツに関する公開データ（Markdown・PDF）を取り込み、**出典付きで回答する RAG チャットボット**。

LLM・ベクトルストアを抽象化し、差し替え可能な設計を採用したポートフォリオ作品。

---

## 技術スタック

| レイヤー | 技術 |
|---|---|
| フロントエンド | Next.js 14（App Router）+ TypeScript |
| バックエンド | FastAPI（Python 3.12） |
| DB / Vector | Supabase（PostgreSQL + pgvector） |
| LLM | Gemini（Google）※ Claude・OpenAI へ差し替え可能 |
| Embedding | OpenAI text-embedding-3-small |
| バッチ | ローカル Docker（Ingest Pipeline） |
| テスト | pytest |
| ホスティング | Vercel（フロント）+ Render（バック） |

---

## セットアップ

詳細は [docs/12_テスト環境構築手順書.md](docs/12_テスト環境構築手順書.md) を参照。

### 1. リポジトリのクローン

```bash
git clone https://github.com/<username>/rag-chatbot.git
cd rag-chatbot
```

### 2. 環境変数の設定

```bash
cp .env.example .env
# .env を編集して DATABASE_URL・GEMINI_API_KEY・OPENAI_API_KEY を設定
```

### 3. バックエンドの起動

```bash
docker compose up backend
```

### 4. フロントエンドの起動

```bash
cd frontend
npm install
npm run dev
```

### 5. データ取り込み

```bash
# data/ にファイルを配置し、batch/sources.yaml にメタ情報を記述してから実行
docker compose run --rm ingest
```

---

## 使い方

1. `http://localhost:3000` にアクセスする
2. 入力欄にスポーツに関する質問を入力して送信する
3. 回答と出典（ドキュメント名・組織名・信頼性スコア）が表示される

---

## ディレクトリ構成

```
rag-chatbot/
├── frontend/     # Next.js アプリ
├── backend/      # FastAPI アプリ
├── batch/        # Ingest バッチ（Docker）
├── data/         # 取り込みデータ（git 管理外）
└── docs/         # 設計ドキュメント
```

詳細は [docs/10_技術スタック.md](docs/10_技術スタック.md) を参照。

---

## 設計ドキュメント

| # | ドキュメント | 工程 | 内容 |
|---|---|---|---|
| 01 | [要件定義](docs/01_要件定義.md) | 要件定義 | ユースケース・機能要件・非機能要件 |
| 02 | [基本設計書](docs/02_基本設計書.md) | 基本設計 | 機能一覧・画面一覧・エンティティ概要・外部連携・非機能要件 |
| 03 | [システム構成図](docs/03_システム構成図.md) | 基本設計 | アーキテクチャ・データフロー・技術採用理由 |
| 04 | [詳細設計書](docs/04_詳細設計書.md) | 詳細設計 | コンポーネント設計・エラーハンドリング・セキュリティ設計 |
| 05 | [テーブルレイアウト](docs/05_テーブルレイアウト.md) | 詳細設計 | DB テーブル定義・DDL・メタ情報設計 |
| 06 | [RAG設計](docs/06_RAG設計.md) | 詳細設計 | チャンク分割・Embedding・プロンプト・LLM抽象層・バッチ処理 |
| 07 | [画面設計](docs/07_画面設計.md) | 詳細設計 | UI レイアウト・出典表示・アクセシビリティ |
| 08 | [API仕様](docs/08_API仕様.md) | 詳細設計 | /chat・/search・/health エンドポイント仕様 |
| 09 | [プログラム仕様書](docs/09_プログラム仕様書.md) | プログラム設計 | モジュール一覧・クラス仕様・環境変数・依存パッケージ |
| 10 | [技術スタック](docs/10_技術スタック.md) | プログラム設計 | 技術一覧・ディレクトリ構成 |
| 11 | [テスト仕様書](docs/11_テスト仕様書.md) | テスト | 単体テスト・統合テスト・モック戦略 |
| 12 | [テスト環境構築手順書](docs/12_テスト環境構築手順書.md) | 環境構築 | ローカル開発環境のセットアップ・テスト実行 |
| 13 | [商用環境構築手順書](docs/13_商用環境構築手順書.md) | 環境構築 | 本番デプロイ（Vercel・Render・Supabase） |
| 14 | [運用マニュアル](docs/14_運用マニュアル.md) | 運用 | 監視・再デプロイ・将来の拡張 |

---

## ライセンス

Copyright (c) 2026 遠藤義之. All rights reserved.  
このソフトウェアの無断複製・配布を禁じます。

