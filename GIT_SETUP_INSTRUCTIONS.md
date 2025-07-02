# GitHubリポジトリ接続手順

このフォルダを既存のGitHubリポジトリ (https://github.com/IKEMENLTD/dify-chat-system) に接続する手順です。

## 前提条件
- Gitがインストールされていること
- GitHubアカウントへのアクセス権限があること

## 手順

### 1. コマンドプロンプトまたはGit Bashを開く

Windowsキー + R → "cmd" または Git Bashを起動

### 2. プロジェクトフォルダに移動

```bash
cd C:\Users\ooxmi\Downloads\Dify自社RAG構築Ver.5.00
```

### 3. Gitリポジトリを初期化

```bash
git init
git branch -m main
```

### 4. .gitignoreファイルを確認

既に作成済みの.gitignoreファイルにSECURITY_WARNING.mdが含まれていることを確認

### 5. リモートリポジトリを追加

```bash
git remote add origin https://github.com/IKEMENLTD/dify-chat-system.git
```

### 6. ファイルをステージング

```bash
git add .
```

### 7. 初回コミット

```bash
git commit -m "Initial commit: Dify Chat System v5.00 with reminder and LINE history features"
```

### 8. GitHubリポジトリの状態を確認

```bash
git fetch origin
git branch -r
```

### 9. プッシュ方法を選択

#### オプションA: 新規リポジトリの場合
```bash
git push -u origin main
```

#### オプションB: 既存のリポジトリを上書きする場合（注意！）
```bash
git push -f origin main
```

#### オプションC: 既存のリポジトリとマージする場合
```bash
git pull origin main --allow-unrelated-histories
# コンフリクトがある場合は解決
git add .
git commit -m "Merge with existing repository"
git push origin main
```

## 重要な注意事項

1. **APIキーの管理**
   - SECURITY_WARNING.mdは.gitignoreに含まれています
   - 環境変数は決してコミットしないでください
   - `.env`ファイルを使用する場合は必ず`.gitignore`に追加

2. **既存リポジトリの確認**
   - 既存のコードがある場合は、オプションCを使用してマージすることを推奨
   - 強制プッシュ（-f）は既存のコミット履歴を失う可能性があります

3. **認証**
   - HTTPSを使用する場合、GitHubのユーザー名とパーソナルアクセストークンが必要
   - SSHキーを設定している場合は、以下のようにSSH URLを使用：
     ```bash
     git remote set-url origin git@github.com:IKEMENLTD/dify-chat-system.git
     ```

## トラブルシューティング

### 権限エラーが発生する場合
- 管理者権限でコマンドプロンプトを実行
- またはGit Bashを使用

### プッシュが拒否される場合
- GitHubリポジトリへの書き込み権限を確認
- パーソナルアクセストークンの権限を確認

### コンフリクトが発生する場合
1. `git status`で競合ファイルを確認
2. 各ファイルを編集して競合を解決
3. `git add <ファイル名>`で解決済みとマーク
4. `git commit`で変更を確定

## 完了後の確認

1. GitHubのリポジトリページで変更が反映されていることを確認
2. Actions（もし設定されていれば）が正常に実行されることを確認
3. READMEやドキュメントを更新

## 今後の開発フロー

```bash
# 変更を加えた後
git add .
git commit -m "変更内容の説明"
git push origin main

# 最新の変更を取得
git pull origin main
```