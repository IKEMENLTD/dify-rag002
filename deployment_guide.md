# 本番環境デプロイメントガイド

## セキュリティ強化版統合AIチャットボット

### 前提条件

- Python 3.9+
- PostgreSQL 12+
- Redis 6+
- SSL/TLS証明書
- python-magic ライブラリ用システム依存関係

### 1. システム準備

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv libmagic1 libmagic-dev

# CentOS/RHEL
sudo yum install -y python3-pip file-devel
```

### 2. アプリケーション設定

```bash
# 仮想環境作成
python3 -m venv venv
source venv/bin/activate

# 依存関係インストール
pip install -r requirements_secure.txt

# 追加セキュリティ依存関係
pip install python-magic flask-sqlalchemy flask-migrate
```

### 3. 環境変数設定

```bash
# 本番環境設定ファイルをコピー
cp .env.production.template .env

# 環境変数を適切に設定
nano .env
```

### 4. 暗号化キー生成

```python
# Python実行で暗号化キーを生成
from cryptography.fernet import Fernet
import secrets

# SECRET_KEY生成
print("SECRET_KEY:", secrets.token_hex(32))

# ENCRYPTION_KEY生成  
print("ENCRYPTION_KEY:", Fernet.generate_key().decode())
```

### 5. データベース初期化

```bash
# データベース作成
python production_secure_main.py
```

### 6. セキュリティ設定確認

#### ファイアウォール設定
```bash
# 必要なポートのみ開放
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 443/tcp  # HTTPS
sudo ufw allow 80/tcp   # HTTP (HTTPS リダイレクト用)
sudo ufw enable
```

#### SSL/TLS設定
- Let's Encrypt または商用証明書を使用
- TLS 1.2以上を強制
- HSTS ヘッダーを有効化

#### ファイルシステム権限
```bash
# アップロードフォルダのセキュリティ設定
sudo mkdir -p /secure/uploads
sudo chown app:app /secure/uploads
sudo chmod 750 /secure/uploads

# .htaccess ファイル配置
echo "deny from all" | sudo tee /secure/uploads/.htaccess
```

### 7. 本番環境起動

#### Gunicorn設定
```bash
# gunicorn.conf.py
bind = "0.0.0.0:5000"
workers = 4
worker_class = "gevent"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2
preload_app = True
```

#### 起動コマンド
```bash
gunicorn -c gunicorn.conf.py production_secure_main:app
```

### 8. リバースプロキシ設定（Nginx）

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;

    # セキュリティヘッダー
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";

    # ファイルアップロード制限
    client_max_body_size 16M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # アップロードファイルへの直接アクセス禁止
    location /secure/uploads/ {
        deny all;
        return 403;
    }
}

# HTTPからHTTPSへのリダイレクト
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

### 9. 監視・ログ設定

#### ログローテーション
```bash
# /etc/logrotate.d/veteranai
/path/to/app.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    postrotate
        systemctl reload veteranai
    endscript
}
```

#### Systemdサービス
```ini
# /etc/systemd/system/veteranai.service
[Unit]
Description=VeteranAI Secure Chatbot
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=app
Group=app
WorkingDirectory=/path/to/app
Environment=PATH=/path/to/app/venv/bin
ExecStart=/path/to/app/venv/bin/gunicorn -c gunicorn.conf.py production_secure_main:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 10. セキュリティチェックリスト

- [ ] 全ての環境変数が適切に設定されている
- [ ] データベース接続が暗号化されている
- [ ] HTTPS が強制されている
- [ ] CSRFプロテクションが有効
- [ ] レート制限が設定されている
- [ ] ファイルアップロードの検証が有効
- [ ] セキュリティヘッダーが設定されている
- [ ] ログが適切に記録されている
- [ ] 管理者アカウントが設定されている
- [ ] バックアップ戦略が確立されている

### 11. 定期メンテナンス

#### セキュリティログ監視
```bash
# 毎日実行
python -c "
from production_secure_main import *
with app.app_context():
    recent_events = SecurityEvent.query.filter(
        SecurityEvent.severity.in_(['high', 'critical']),
        SecurityEvent.created_at >= datetime.utcnow() - timedelta(days=1)
    ).all()
    if recent_events:
        print(f'高リスクイベント: {len(recent_events)}件')
"
```

#### 依存関係更新
```bash
# 月次実行
pip-audit  # 脆弱性チェック
pip list --outdated  # 更新可能パッケージ確認
```

### トラブルシューティング

#### よくある問題

1. **python-magic エラー**
   ```bash
   sudo apt-get install libmagic1
   pip install python-magic
   ```

2. **PostgreSQL接続エラー**
   - 接続文字列を確認
   - ファイアウォール設定を確認
   - SSL証明書を確認

3. **Redis接続エラー**
   - Redis サービス状態確認
   - 接続URL設定確認

### サポート

セキュリティに関する問題が発生した場合は、即座にアプリケーションを停止し、ログを確認してください。