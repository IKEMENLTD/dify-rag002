#!/bin/bash

# ベテランAI セットアップスクリプト
set -e

echo "🚀 ベテランAI セットアップを開始します..."
echo "📅 $(date)"
echo ""

# 環境チェック
echo "📋 環境をチェックしています..."

# Python バージョンチェック
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 が見つかりません。Python 3.8以上をインストールしてください。"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.8"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python 3.8以上が必要です。現在のバージョン: $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION が見つかりました"

# Node.js バージョンチェック
if ! command -v node &> /dev/null; then
    echo "❌ Node.js が見つかりません。Node.js 16以上をインストールしてください。"
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 16 ]; then
    echo "❌ Node.js 16以上が必要です。現在のバージョン: $(node --version)"
    exit 1
fi

echo "✅ Node.js $(node --version) が見つかりました"

# 必要なシステムパッケージをインストール
echo "📦 システムパッケージをインストールしています..."

if command -v apt-get &> /dev/null; then
    # Ubuntu/Debian
    sudo apt-get update
    sudo apt-get install -y \
        tesseract-ocr tesseract-ocr-jpn tesseract-ocr-eng \
        poppler-utils ffmpeg libpq-dev build-essential
elif command -v yum &> /dev/null; then
    # CentOS/RHEL
    sudo yum install -y \
        tesseract tesseract-langpack-jpn tesseract-langpack-eng \
        poppler-utils ffmpeg-devel postgresql-devel gcc
elif command -v brew &> /dev/null; then
    # macOS
    brew install tesseract tesseract-lang poppler ffmpeg postgresql
else
    echo "⚠️  サポートされていないパッケージマネージャです。手動でTesseract、Poppler、FFmpegをインストールしてください。"
fi

# Python仮想環境の作成
echo "🐍 Python仮想環境を作成しています..."
python3 -m venv venv
source venv/bin/activate

# Python依存関係のインストール
echo "📦 Python依存関係をインストールしています..."
pip install --upgrade pip
pip install -r requirements.txt

# Node.js依存関係のインストール
echo "📦 Node.js依存関係をインストールしています..."
cd frontend
npm install

# フロントエンド環境変数設定
if [ ! -f .env.local ]; then
    cp .env.local.example .env.local
    echo "📝 フロントエンド用.env.localファイルが作成されました。"
fi

cd ..

# 環境変数ファイルの作成
echo "⚙️  環境設定ファイルを作成しています..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "📝 .env ファイルが作成されました。必要な API キーを設定してください。"
else
    echo "✅ .env ファイルが既に存在します"
fi

# ディレクトリの作成
echo "📁 必要なディレクトリを作成しています..."
mkdir -p uploads logs

# データベーススキーマの初期化（オプション）
echo "🗄️  データベーススキーマの初期化は、Supabaseの設定完了後に行ってください。"

echo ""
echo "🎉 セットアップが完了しました！"
echo ""
echo "次の手順:"
echo "1. .env ファイルを編集して、必要なAPI キーを設定してください"
echo "2. Supabaseプロジェクトを作成し、データベース情報を設定してください"
echo "3. backend/database/schema.sql をSupabaseで実行してください"
echo "4. backend/database/functions.sql をSupabaseで実行してください"
echo ""
echo "開発サーバーの起動:"
echo "  Backend:  cd backend && python main.py"
echo "  Frontend: cd frontend && npm run dev"
echo ""
echo "Docker での起動:"
echo "  docker-compose up --build"
echo ""