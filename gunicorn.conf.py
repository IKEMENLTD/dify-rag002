# ============================================================================
# Gunicorn本番環境設定 - production_secure_main.py用
# ============================================================================

import os
import multiprocessing

# サーバー設定
bind = "0.0.0.0:5000"
backlog = 2048

# ワーカー設定
workers = min(multiprocessing.cpu_count() * 2 + 1, 8)  # 最大8ワーカー
worker_class = "gevent"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100

# タイムアウト設定
timeout = 30
keepalive = 2
graceful_timeout = 30

# パフォーマンス
preload_app = True
max_worker_memory = 100  # MB

# セキュリティ
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# ログ設定
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# プロセス管理
pidfile = "/var/run/gunicorn/veteranai.pid"
user = "app"
group = "app"
tmp_upload_dir = None

# SSL設定（必要に応じて）
# keyfile = "/path/to/key.pem"
# certfile = "/path/to/cert.pem"

# 環境変数
raw_env = [
    "FLASK_ENV=production",
]

# セキュリティ強化
def when_ready(server):
    """サーバー準備完了時の処理"""
    server.log.info("Secure production server is ready. Listening on: %s", server.address)

def worker_int(worker):
    """ワーカープロセスが中断された時の処理"""
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    """ワーカーフォーク前の処理"""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    """ワーカーフォーク後の処理"""
    server.log.info("Worker ready (pid: %s)", worker.pid)

def worker_abort(worker):
    """ワーカー異常終了時の処理"""
    worker.log.info("Worker aborted (pid: %s)", worker.pid)