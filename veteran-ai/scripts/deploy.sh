#!/bin/bash

# ベテランAI デプロイスクリプト
set -e

echo "🚀 ベテランAI デプロイを開始します..."

# 環境変数の確認
check_env_var() {
    if [ -z "${!1}" ]; then
        echo "❌ 環境変数 $1 が設定されていません"
        exit 1
    fi
}

echo "📋 必要な環境変数をチェックしています..."
check_env_var "SUPABASE_URL"
check_env_var "SUPABASE_KEY"
check_env_var "OPENAI_API_KEY"

echo "✅ 環境変数チェック完了"

# フロントエンドのビルド
echo "🏗️  フロントエンドをビルドしています..."
cd frontend
npm ci --only=production
npm run build
cd ..

# バックエンドの依存関係チェック
echo "📦 バックエンドの依存関係をチェックしています..."
pip install --upgrade pip
pip install -r requirements.txt

# データベース接続テスト
echo "🗄️  データベース接続をテストしています..."
python3 -c "
import os
from supabase import create_client, Client
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')
supabase = create_client(url, key)
try:
    result = supabase.table('documents').select('count').limit(1).execute()
    print('✅ データベース接続成功')
except Exception as e:
    print(f'❌ データベース接続失敗: {e}')
    exit(1)
"

# アプリケーションの起動テスト
echo "🧪 アプリケーションの起動テストを実行しています..."
timeout 10s python backend/main.py &
PID=$!
sleep 5

if kill -0 $PID 2>/dev/null; then
    echo "✅ アプリケーション起動成功"
    kill $PID
else
    echo "❌ アプリケーション起動失敗"
    exit 1
fi

# Dockerイメージのビルド（オプション）
if command -v docker &> /dev/null; then
    echo "🐳 Dockerイメージをビルドしています..."
    docker build -t veteran-ai:latest .
    echo "✅ Dockerイメージビルド完了"
fi

echo ""
echo "🎉 デプロイ準備が完了しました！"
echo ""
echo "デプロイオプション:"
echo ""
echo "1. Render デプロイ:"
echo "   - render.yaml を確認してください"
echo "   - Render ダッシュボードでサービスを作成してください"
echo ""
echo "2. Docker デプロイ:"
echo "   docker-compose up -d"
echo ""
echo "3. 手動デプロイ:"
echo "   python backend/main.py"
echo ""