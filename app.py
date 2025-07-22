from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import json

app = Flask(__name__)
CORS(app)

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
                
                console.log('Sending message:', message);
                addMessage(message, 'user');
                input.value = '';
                
                fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: message})
                })
                .then(response => {
                    console.log('Response status:', response.status);
                    return response.json();
                })
                .then(data => {
                    console.log('Response data:', data);
                    addMessage(data.response || 'エラーが発生しました', 'assistant');
                })
                .catch(error => {
                    console.error('Fetch error:', error);
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
        
        print(f"Received message: {message}")
        
        # Default response
        response = f"受信しました: {message}"
        
        # Debug: Check environment variables
        dify_api_key = os.getenv('DIFY_API_KEY')
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        
        print(f"Dify API Key exists: {bool(dify_api_key)}")
        print(f"Anthropic API Key exists: {bool(anthropic_key)}")
        
        if not dify_api_key and not anthropic_key:
            response = "APIキーが設定されていません。環境変数を確認してください。"
        elif dify_api_key:
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
                
                # Use completion-messages endpoint instead
                print(f"Calling Dify API with payload: {payload}")
                resp = requests.post(
                    'https://api.dify.ai/v1/completion-messages',
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                print(f"Dify API response status: {resp.status_code}")
                print(f"Dify API response: {resp.text[:200]}")
                
                if resp.status_code == 200:
                    data = resp.json()
                    response = data.get('answer', response)
                elif resp.status_code == 400:
                    # Dify app unavailable, use Claude instead
                    pass
                elif resp.status_code == 403:
                    response = f"Dify API認証エラー (403): APIキーを確認してください"
                elif resp.status_code == 404:
                    response = f"Dify APIエンドポイントエラー (404)"
                else:
                    response = f"Dify APIエラー ({resp.status_code}): {resp.text[:100]}"
                    
                # If Dify fails, try Claude
                if resp.status_code != 200 and anthropic_key:
                        claude_headers = {
                            'x-api-key': anthropic_key,
                            'anthropic-version': '2023-06-01',
                            'content-type': 'application/json'
                        }
                        claude_payload = {
                            'model': 'claude-3-sonnet-20240229',
                            'messages': [{'role': 'user', 'content': message}],
                            'max_tokens': 1000
                        }
                        claude_resp = requests.post(
                            'https://api.anthropic.com/v1/messages',
                            headers=claude_headers,
                            json=claude_payload,
                            timeout=30
                        )
                        if claude_resp.status_code == 200:
                            claude_data = claude_resp.json()
                            response = claude_data['content'][0]['text']
            except Exception as e:
                response = f"APIエラー: {str(e)[:100]}"
                # Try Claude as fallback on exception
                if anthropic_key:
                    try:
                        claude_headers = {
                            'x-api-key': anthropic_key,
                            'anthropic-version': '2023-06-01',
                            'content-type': 'application/json'
                        }
                        claude_payload = {
                            'model': 'claude-3-sonnet-20240229',
                            'messages': [{'role': 'user', 'content': message}],
                            'max_tokens': 1000
                        }
                        claude_resp = requests.post(
                            'https://api.anthropic.com/v1/messages',
                            headers=claude_headers,
                            json=claude_payload,
                            timeout=30
                        )
                        if claude_resp.status_code == 200:
                            claude_data = claude_resp.json()
                            response = claude_data['content'][0]['text']
                    except:
                        pass
        
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/line', methods=['POST'])
def line_webhook():
    """Simple LINE webhook handler"""
    return 'OK', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)