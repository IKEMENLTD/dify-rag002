#!/bin/bash

# GitHubリポジトリに接続するためのセットアップスクリプト

echo "=== Dify Chat System Git Setup ==="
echo ""

# 現在のディレクトリを確認
echo "現在のディレクトリ: $(pwd)"
echo ""

# Gitがインストールされているか確認
if ! command -v git &> /dev/null; then
    echo "エラー: Gitがインストールされていません"
    echo "以下のコマンドでインストールしてください:"
    echo "  Windows: https://git-scm.com/download/win"
    exit 1
fi

echo "Gitのバージョン: $(git --version)"
echo ""

# .gitフォルダが既に存在するか確認
if [ -d ".git" ]; then
    echo "警告: 既にGitリポジトリが初期化されています"
    echo "既存のリポジトリ情報:"
    git remote -v
    echo ""
    read -p "続行しますか？ (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    # Gitリポジトリを初期化
    echo "Gitリポジトリを初期化中..."
    git init
    echo ""
fi

# mainブランチに変更
echo "mainブランチに切り替え中..."
git branch -m main 2>/dev/null || git checkout -b main
echo ""

# リモートリポジトリを追加
echo "GitHubリポジトリを追加中..."
git remote remove origin 2>/dev/null
git remote add origin https://github.com/IKEMENLTD/dify-chat-system.git
echo ""

# .gitignoreファイルを作成
echo ".gitignoreファイルを作成中..."
cat > .gitignore << 'EOL'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
dify_chat_env/
.venv/

# Environment variables
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Database
*.db
*.sqlite
*.sqlite3

# Sensitive files
secrets/
private/
*.pem
*.key

# Temporary files
tmp/
temp/
*.tmp
*.temp

# Build files
dist/
build/
*.egg-info/

# Testing
.coverage
.pytest_cache/
htmlcov/

# Security warning (APIキーが含まれているため)
SECURITY_WARNING.md
EOL

echo ".gitignore作成完了"
echo ""

# 初回コミットの準備
echo "ファイルをステージング中..."
git add .
echo ""

# 現在の状態を表示
echo "=== 現在のGit状態 ==="
git status
echo ""

echo "=== セットアップ完了 ==="
echo ""
echo "次のステップ:"
echo "1. 以下のコマンドで初回コミットを作成:"
echo "   git commit -m \"Initial commit: Dify Chat System v5.00\""
echo ""
echo "2. GitHubの最新状態を取得:"
echo "   git fetch origin"
echo ""
echo "3. リモートブランチの状態を確認:"
echo "   git branch -r"
echo ""
echo "4. 以下のいずれかの方法でプッシュ:"
echo "   a) 新規リポジトリの場合:"
echo "      git push -u origin main"
echo ""
echo "   b) 既存のリポジトリに上書きする場合:"
echo "      git push -f origin main"
echo ""
echo "   c) 既存のリポジトリとマージする場合:"
echo "      git pull origin main --allow-unrelated-histories"
echo "      (コンフリクトを解決)"
echo "      git push origin main"
echo ""
echo "注意: SECURITY_WARNING.mdファイルは.gitignoreに追加されています"
echo "      APIキーは環境変数で管理してください"