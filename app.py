from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
def home():
    port = os.environ.get('PORT', '5000')
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>ベテランAI</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; text-align: center; }}
            h1 {{ color: #1d4ed8; }}
            .status {{ background: #f0f9ff; padding: 20px; border-radius: 10px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <h1>🤖 ベテランAI</h1>
        <div class="status">
            <p>✅ サーバーが正常に動作しています</p>
            <p>🌐 Port: {port}</p>
        </div>
        <p><a href="/ping">Ping Test</a></p>
        <p><a href="/dashboard">Dashboard</a></p>
    </body>
    </html>
    """

@app.route('/ping')
def ping():
    return "pong - ベテランAI is alive!"

@app.route('/dashboard')
def dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ベテランAI Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f8fafc; }
            .card { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin: 20px 0; }
            h1 { color: #1d4ed8; text-align: center; }
        </style>
    </head>
    <body>
        <h1>📊 ベテランAI Dashboard</h1>
        <div class="card">
            <h2>✅ システム状態</h2>
            <p>サーバー: 正常稼働中</p>
            <p>サービス: ベテランAI</p>
            <p>バージョン: 1.0.0</p>
        </div>
        <div class="card">
            <h2>🔗 リンク</h2>
            <p><a href="/">ホーム</a></p>
            <p><a href="/ping">Ping Test</a></p>
        </div>
    </body>
    </html>
    """

# gunicorn用に削除 - gunicornは__main__ブロックを実行しない
# if __name__ == '__main__':
#     port = int(os.environ.get('PORT', 5000))
#     print(f"🚀 ベテランAI starting on port {port}")
#     app.run(host='0.0.0.0', port=port, debug=False)