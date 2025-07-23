# 🔐 セキュリティ設定ガイド

## ⚠️ 重要：本番環境デプロイ前に必ず実施

### 1. **環境変数の設定**

本番環境では以下の環境変数を必ず変更してください：

```bash
# 強力なランダム文字列に変更
SECRET_KEY=your-super-secret-key-change-this-in-production

# 本番ドメインのみに制限
ALLOWED_ORIGINS=https://yourdomain.com

# 全てのAPIキーを再発行
DIFY_API_KEY=新しいAPIキー
LINE_ACCESS_TOKEN=新しいトークン
LINE_SECRET=新しいシークレット
```

### 2. **認証システムの実装**

現在、認証システムが未実装です。本番環境では必須：

```python
# 例：JWT認証の実装
from flask_jwt_extended import JWTManager, jwt_required

app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
jwt = JWTManager(app)

@app.route('/api/protected', methods=['GET'])
@jwt_required()
def protected():
    # 認証済みユーザーのみアクセス可能
    pass
```

### 3. **レート制限の実装**

DDoS攻撃を防ぐため：

```bash
pip install Flask-Limiter
```

```python
from flask_limiter import Limiter
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["100 per hour", "10 per minute"]
)
```

### 4. **データベースセキュリティ**

- Supabaseの行レベルセキュリティ（RLS）を有効化
- 各テーブルにユーザーアクセス制限を設定

### 5. **HTTPS必須化**

```python
@app.before_request
def force_https():
    if not request.is_secure and app.env != 'development':
        return redirect(request.url.replace('http://', 'https://'))
```

### 6. **監視とログ**

- エラー監視サービス（Sentry等）の導入
- アクセスログの記録と分析

## 🚨 現在の制限事項

1. **APIエンドポイントが無認証**
   - `/api/conversations` - 他人の会話履歴にアクセス可能
   - `/api/reminders` - 他人のリマインダーにアクセス可能

2. **ユーザー分離が不完全**
   - user_idパラメータを信頼している
   - セッション管理が必要

3. **本番クレデンシャルの即時変更が必要**
   - 現在の.envファイルの値は公開されている
   - 全てのAPIキーとパスワードを再発行

## ✅ 実装済みのセキュリティ対策

- 入力値検証とサニタイゼーション
- XSS防止
- セキュリティヘッダー設定
- CORS制限
- LINE Webhook署名検証
- エラーハンドリング

## 📋 本番環境チェックリスト

- [ ] 全ての環境変数を本番用に変更
- [ ] .envファイルをgitから削除
- [ ] 認証システムを実装
- [ ] レート制限を設定
- [ ] Supabase RLSを有効化
- [ ] HTTPS化
- [ ] 監視システムを導入
- [ ] ペネトレーションテストを実施