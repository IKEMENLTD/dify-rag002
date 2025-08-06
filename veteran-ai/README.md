# ベテランAI - 社内非構造情報統合ナレッジ支援システム

## 概要
Slack、LINE、Chatwork等のチャット履歴、PDF・画像・音声などの非構造社内情報を統合し、意味ベースで検索・回答可能にする生成AIナレッジ支援システム。

## 主要機能
- 複数チャットツールからのデータ自動取得
- 画像・PDF（OCR）、音声（Whisper）のテキスト化
- ベクトル検索による意味検索
- RAG構成による文脈付き回答生成
- 引用元情報付きWeb UI
- Slackボット統合

## 技術スタック
- **Database**: Supabase + pgvector
- **Backend**: FastAPI + Python
- **OCR**: Tesseract
- **ASR**: OpenAI Whisper
- **Embedding**: OpenAI text-embedding-3-small
- **LLM**: GPT-4 / Claude
- **RAG**: Dify
- **Frontend**: React + TypeScript
- **Deploy**: Render

## アーキテクチャ
```
[チャットツール] → [データ取得] → [前処理] → [Embedding] → [Vector DB]
                                                                    ↓
[Web UI] ← [回答生成] ← [RAG処理] ← [ベクトル検索] ←────────────────┘
```

## 🚀 クイックスタート

### 1. 自動セットアップ
```bash
# 開発環境セットアップ
git clone <repository-url>
cd veteran-ai
./scripts/setup.sh

# 本番環境セットアップ
./scripts/setup.sh --production
```

### 2. 環境変数設定
```bash
# バックエンド環境変数
cp .env.example .env
# 必要なAPI キーを.envに設定

# フロントエンド環境変数  
cd frontend
cp .env.local.example .env.local
# API URLを設定
```

### 3. データベース初期化
```sql
-- Supabaseのクエリエディタで実行
-- 1. スキーマ作成
\i backend/database/schema.sql

-- 2. 関数作成  
\i backend/database/functions.sql
```

### 4. サービス起動
```bash
# 開発環境
python backend/main.py        # バックエンド (8000番ポート)
cd frontend && npm run dev     # フロントエンド (3000番ポート)

# 本番環境（Docker）
docker-compose up --build
```

## ディレクトリ構造
```
veteran-ai/
├── backend/           # FastAPI backend
├── frontend/          # React frontend  
├── data-ingestion/    # データ取得・処理
├── vector-search/     # ベクトル検索エンジン
├── rag-engine/        # RAG処理エンジン
├── integrations/      # 外部連携（Slack等）
├── docker/           # Docker設定
└── deploy/           # デプロイ設定
```