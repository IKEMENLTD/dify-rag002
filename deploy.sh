#!/bin/bash

# ベテランAI Ver.003 - 自動デプロイスクリプト
# 使い方: ./deploy.sh "コミットメッセージ"

echo "🚀 ベテランAI 自動デプロイを開始します..."

# コミットメッセージの確認
if [ -z "$1" ]; then
    echo "❌ エラー: コミットメッセージを指定してください"
    echo "使い方: ./deploy.sh \"コミットメッセージ\""
    exit 1
fi

# Gitの状態確認
echo "📋 変更ファイルを確認中..."
git status

# 変更がない場合は終了
if [ -z "$(git status --porcelain)" ]; then
    echo "✅ 変更はありません。デプロイをスキップします。"
    exit 0
fi

# 変更をステージング
echo "📦 変更をステージング中..."
git add -A

# コミット
echo "💾 コミット中..."
git commit -m "$1

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"

# プッシュ
echo "📤 GitHubにプッシュ中..."
git push origin main

# 成功メッセージ
echo "✅ プッシュ完了！"
echo "🔄 Renderが自動的にデプロイを開始します。"
echo "⏱️  デプロイ完了まで約2-3分お待ちください。"
echo ""
echo "📊 デプロイ状況の確認："
echo "https://dashboard.render.com/web/srv-cu1s09m8ii6s739pa250/events"
echo ""
echo "🌐 サイトURL："
echo "https://veteranai-final-test.onrender.com"