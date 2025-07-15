import os
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import logging

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flaskアプリ初期化
app = Flask(__name__, static_folder='.')
CORS(app, origins=['*'])

# 環境変数読み込み
DIFY_API_KEY = os.getenv('DIFY_API_KEY')
DIFY_API_URL = os.getenv('DIFY_API_URL', 'https://api.dify.ai/v1')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')

# Supabase設定
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')

# Supabaseクライアント初期化
supabase_client = None
if SUPABASE_URL and SUPABASE_ANON_KEY:
    try:
        from supabase import create_client
        supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        logger.info("Supabaseクライアント初期化成功")
    except Exception as e:
        logger.error(f"Supabaseクライアント初期化失敗: {e}")

def call_dify_api(user_message):
    """Dify APIを呼び出し"""
    if not DIFY_API_KEY:
        return None
    
    try:
        headers = {
            'Authorization': f'Bearer {DIFY_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            "inputs": {"query": user_message},
            "query": user_message,
            "response_mode": "blocking",
            "conversation_id": "",
            "user": "web_user"
        }
        
        response = requests.post(
            f"{DIFY_API_URL}/chat-messages",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('answer', '')
        else:
            logger.error(f"Dify API エラー: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Dify API呼び出しエラー: {e}")
        return None

def call_claude_api(user_message):
    """Claude APIを呼び出し"""
    if not ANTHROPIC_API_KEY:
        return None
    
    try:
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01'
        }
        
        data = {
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 2000,
            "temperature": 0.7,
            "messages": [{"role": "user", "content": user_message}]
        }
        
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['content'][0]['text']
        else:
            logger.error(f"Claude API エラー: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Claude API呼び出しエラー: {e}")
        return None

def generate_ai_response(user_message):
    """AI回答生成"""
    # Dify APIを優先
    if DIFY_API_KEY:
        response = call_dify_api(user_message)
        if response:
            return response
    
    # Claude APIフォールバック
    if ANTHROPIC_API_KEY:
        response = call_claude_api(user_message)
        if response:
            return response
    
    # フォールバック回答
    return "申し訳ございません。現在AIサービスが利用できません。後ほど再度お試しください。"

@app.route('/')
def index():
    """メインページ"""
    return send_from_directory('.', 'index.html')

@app.route('/dashboard')
def dashboard():
    """ダッシュボード"""
    return send_from_directory('.', 'dashboard.html')

@app.route('/health')
def health_check():
    """ヘルスチェック"""
    try:
        status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        }
        
        # 環境変数チェック
        if not SECRET_KEY:
            status["status"] = "unhealthy"
            status["error"] = "SECRET_KEY not configured"
        
        # データベースチェック
        if supabase_client:
            try:
                supabase_client.table('conversations').select('*').limit(1).execute()
                status["database"] = "connected"
            except:
                status["database"] = "disconnected"
        else:
            status["database"] = "not configured"
        
        return jsonify(status), 200 if status["status"] == "healthy" else 503
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/ready')
def ready():
    """レディネスチェック"""
    return jsonify({
        "ready": True,
        "timestamp": datetime.now().isoformat()
    }), 200

@app.route('/chat', methods=['POST'])
def chat():
    """チャットエンドポイント"""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'メッセージが必要です'}), 400
        
        user_message = data['message']
        
        # AI回答生成
        ai_response = generate_ai_response(user_message)
        
        # 簡単な会話保存
        if supabase_client:
            try:
                supabase_client.table('conversations').insert({
                    'user_id': 'web_user',
                    'user_message': user_message,
                    'ai_response': ai_response,
                    'created_at': datetime.now().isoformat()
                }).execute()
            except Exception as e:
                logger.error(f"データベース保存エラー: {e}")
        
        return jsonify({
            'response': ai_response,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"チャットエラー: {e}")
        return jsonify({'error': 'サーバーエラーが発生しました'}), 500

@app.route('/api/stats')
def stats():
    """統計情報"""
    try:
        if not supabase_client:
            return jsonify({'error': 'Database not available'}), 503
        
        # 今日の会話数
        today = datetime.now().date()
        result = supabase_client.table('conversations').select('*', count='exact').gte('created_at', today.isoformat()).execute()
        
        stats_data = {
            'conversations_today': result.count or 0,
            'status': 'success'
        }
        
        return jsonify(stats_data)
        
    except Exception as e:
        logger.error(f"統計取得エラー: {e}")
        return jsonify({'error': 'Failed to get stats'}), 500

if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"アプリケーション開始: PORT={port}")
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logger.error(f"アプリケーション開始エラー: {e}")