# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import json
import re

app = Flask(__name__)
CORS(app)

def clean_response(text):
    """Remove thinking tags and clean up the response"""
    if not text:
        return text
    
    # Remove <think>...</think> tags and their content (case insensitive)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Basic formatting improvements for readability
    text = text.replace('。 ', '。\n\n')  # Period + space -> Period + double newline
    text = text.replace('？ ', '？\n\n')  # Question + space -> Question + double newline  
    text = text.replace('！ ', '！\n\n')  # Exclamation + space -> Exclamation + double newline
    text = text.replace('【', '\n\n【')   # Section headers
    text = text.replace('▼', '\n\n▼')    # Subsection markers
    
    # Clean up excessive whitespace
    text = re.sub(r'[ \t]+', ' ', text)      # Multiple spaces/tabs to single space
    text = re.sub(r'\n{3,}', '\n\n', text)   # Multiple newlines to double
    text = text.strip()
    
    return text

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ベテランAI</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; text-align: center; }
            h1 { color: #1d4ed8; }
            .status { background: #f0f9ff; padding: 20px; border-radius: 10px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <h1>🤖 ベテランAI</h1>
        <div class="status">
            <p>✅ サーバーが正常に動作しています</p>
        </div>
        <p><a href="/ping">Ping Test</a></p>
        <p><a href="/chat">チャット</a></p>
        <p><a href="/api/status">API Status</a></p>
        <p><a href="/test">テストページ</a></p>
    </body>
    </html>
    """

@app.route('/ping')
def ping():
    return "pong - ベテランAI is alive!"

@app.route('/api/status')
def api_status():
    """Check API configuration status"""
    return jsonify({
        'status': 'ok',
        'dify_configured': bool(os.getenv('DIFY_API_KEY')),
        'claude_configured': bool(os.getenv('ANTHROPIC_API_KEY')),
        'dify_key_prefix': os.getenv('DIFY_API_KEY', '')[:10] + '...' if os.getenv('DIFY_API_KEY') else 'Not set',
        'environment': os.getenv('NODE_ENV', 'production')
    })

@app.route('/test')
def test_page():
    """Test page to check API configuration"""
    dify_key = os.getenv('DIFY_API_KEY')
    claude_key = os.getenv('ANTHROPIC_API_KEY')
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>API Test Page</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .status {{ padding: 10px; margin: 10px 0; border-radius: 5px; }}
            .ok {{ background: #d4edda; color: #155724; }}
            .error {{ background: #f8d7da; color: #721c24; }}
        </style>
    </head>
    <body>
        <h1>🔧 API設定テスト</h1>
        
        <div class="status {'ok' if dify_key else 'error'}">
            Dify API: {'✅ 設定済み' if dify_key else '❌ 未設定'}
            {f' (Key: {dify_key[:10]}...)' if dify_key else ''}
        </div>
        
        <div class="status {'ok' if claude_key else 'error'}">
            Claude API: {'✅ 設定済み' if claude_key else '❌ 未設定'}
            {f' (Key: {claude_key[:15]}...)' if claude_key else ''}
        </div>
        
        <h2>テスト送信</h2>
        <button onclick="testAPI()">APIテスト実行</button>
        <button onclick="testDifyDirect()">Dify直接テスト</button>
        <div id="result"></div>
        
        <script>
            async function testAPI() {{
                const result = document.getElementById('result');
                result.innerHTML = 'テスト中...';
                
                try {{
                    const response = await fetch('/api/chat', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{message: 'テストメッセージ'}})
                    }});
                    
                    const data = await response.json();
                    result.innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
                }} catch (error) {{
                    result.innerHTML = 'エラー: ' + error.message;
                }}
            }}
            
            async function testDifyDirect() {{
                const result = document.getElementById('result');
                result.innerHTML = 'Difyテスト中...';
                
                try {{
                    const response = await fetch('/api/dify-test', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{message: 'テスト'}})
                    }});
                    
                    const data = await response.json();
                    result.innerHTML = '<h3>Dify直接テスト結果:</h3><pre>' + JSON.stringify(data, null, 2) + '</pre>';
                }} catch (error) {{
                    result.innerHTML = 'Dify直接テストエラー: ' + error.message;
                }}
            }}
        </script>
        
        <p><a href="/">ホームに戻る</a></p>
    </body>
    </html>
    """

@app.route('/chat')
def chat():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ベテランAI チャット</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
            h1 { color: #1d4ed8; text-align: center; }
            #chat-container { max-width: 600px; margin: 0 auto; }
            #messages { height: 400px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; margin-bottom: 10px; }
            .message { margin: 10px 0; padding: 10px; border-radius: 10px; }
            .user { background: #1d4ed8; color: white; text-align: right; }
            .assistant { background: #f0f0f0; }
            #input-container { display: flex; gap: 10px; }
            #message-input { flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
            #send-button { padding: 10px 20px; background: #1d4ed8; color: white; border: none; border-radius: 5px; cursor: pointer; }
        </style>
    </head>
    <body>
        <h1>🤖 ベテランAI チャット</h1>
        <div id="chat-container">
            <div id="messages"></div>
            <div id="input-container">
                <input type="text" id="message-input" placeholder="メッセージを入力..." onkeypress="if(event.key==='Enter')sendMessage()">
                <button id="send-button" onclick="sendMessage()">送信</button>
            </div>
        </div>
        <script>
            function sendMessage() {
                const input = document.getElementById('message-input');
                const message = input.value.trim();
                if (!message) return;
                
                addMessage(message, 'user');
                input.value = '';
                
                fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: message})
                })
                .then(response => response.json())
                .then(data => {
                    addMessage(data.response || 'エラーが発生しました', 'assistant');
                })
                .catch(error => {
                    addMessage('通信エラーが発生しました', 'assistant');
                });
            }
            
            function addMessage(text, type) {
                const messages = document.getElementById('messages');
                const div = document.createElement('div');
                div.className = 'message ' + type;
                div.textContent = text;
                messages.appendChild(div);
                messages.scrollTop = messages.scrollHeight;
            }
        </script>
    </body>
    </html>
    """

@app.route('/api/chat', methods=['POST'])
def api_chat():
    try:
        data = request.get_json()
        message = data.get('message', '')
        
        # Default response
        response = f"受信しました: {message}"
        
        # Check environment variables
        dify_api_key = os.getenv('DIFY_API_KEY')
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        
        if not dify_api_key and not anthropic_key:
            response = "APIキーが設定されていません。環境変数を確認してください。"
        
        # Try Dify first
        if dify_api_key:
            try:
                headers = {
                    'Authorization': f'Bearer {dify_api_key}',
                    'Content-Type': 'application/json'
                }
                payload = {
                    'inputs': {},
                    'query': message,
                    'response_mode': 'blocking',
                    'conversation_id': '',
                    'user': 'web-user'
                }
                # Try chat-messages first (for chatbots)
                resp = requests.post(
                    'https://api.dify.ai/v1/chat-messages',
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                # If chat-messages fails, try completion-messages (for text generation)
                if resp.status_code != 200:
                    resp = requests.post(
                        'https://api.dify.ai/v1/completion-messages',
                        headers=headers,
                        json=payload,
                        timeout=30
                    )
                
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        raw_response = data.get('answer', response)
                        response = clean_response(raw_response)
                    except Exception as e:
                        response = f"JSON解析エラー: {str(e)}"
                else:
                    # Parse error for better user feedback
                    try:
                        error_data = resp.json()
                        if 'anthropic' in error_data.get('message', '').lower():
                            response = f"🔧 AI設定エラーです。Difyでモデル設定を確認してください。メッセージ: {message}"
                        elif 'app_unavailable' in error_data.get('code', ''):
                            response = f"🔧 アプリが公開状態ではありません。Difyで公開設定を確認してください。メッセージ: {message}"
                        else:
                            response = f"🤖 一時的にサービスが利用できません。メッセージ: {message}"
                    except:
                        response = f"🤖 一時的にサービスが利用できません。メッセージ: {message}"
            except Exception as e:
                response = f"Dify APIエラー: {str(e)[:100]}"
        
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dify-test', methods=['POST'])
def dify_direct_test():
    """Direct Dify API test with detailed response"""
    try:
        data = request.get_json()
        message = data.get('message', 'Hello')
        
        dify_api_key = os.getenv('DIFY_API_KEY')
        if not dify_api_key:
            return jsonify({'error': 'Dify API key not found'})
        
        headers = {
            'Authorization': f'Bearer {dify_api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'inputs': {},
            'query': message,
            'response_mode': 'blocking',
            'conversation_id': '',
            'user': 'test-user'
        }
        
        # Test chat-messages endpoint
        chat_resp = requests.post(
            'https://api.dify.ai/v1/chat-messages',
            headers=headers,
            json=payload,
            timeout=30
        )
        
        # Test completion-messages endpoint
        completion_resp = requests.post(
            'https://api.dify.ai/v1/completion-messages',
            headers=headers,
            json=payload,
            timeout=30
        )
        
        return jsonify({
            'chat_endpoint': {
                'status_code': chat_resp.status_code,
                'response': chat_resp.text[:500],
                'success': chat_resp.status_code == 200
            },
            'completion_endpoint': {
                'status_code': completion_resp.status_code,
                'response': completion_resp.text[:500],
                'success': completion_resp.status_code == 200
            },
            'api_key_prefix': dify_api_key[:10] + '...'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/webhook/line', methods=['POST'])
def line_webhook():
    """LINE webhook handler - only responds to messages containing 'ベテランAI'"""
    try:
        body = request.get_json()
        
        if not body or 'events' not in body:
            return 'OK', 200
        
        for event in body['events']:
            if event.get('type') == 'message' and event.get('message', {}).get('type') == 'text':
                message_text = event.get('message', {}).get('text', '')
                
                # Only respond if message contains "ベテランAI"
                if 'ベテランAI' in message_text:
                    # Process the message through our chat API
                    # For now, just acknowledge - actual LINE response would need LINE Bot SDK
                    pass
        
        return 'OK', 200
    except Exception as e:
        return 'OK', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)