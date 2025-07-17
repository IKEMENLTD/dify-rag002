from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import os
import json
import requests
from config import Config
from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)
CORS(app, origins=app.config['CORS_ORIGINS'])

# Register LINE Bot blueprint
try:
    from line_bot import line_bot_bp
    app.register_blueprint(line_bot_bp)
except Exception as e:
    app.logger.warning(f"Could not initialize LINE Bot: {str(e)}")

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
            <p><a href="/chat">チャット</a></p>
        </div>
    </body>
    </html>
    """

@app.route('/chat')
def chat_interface():
    """Chat interface"""
    return render_template_string(CHAT_TEMPLATE)

@app.route('/api/chat', methods=['POST'])
def chat_api():
    """Handle chat API requests"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        
        if not message:
            return jsonify({'error': 'メッセージが必要です'}), 400
        
        # Try Dify first
        response = call_dify_api(message)
        
        if not response:
            # Fallback to Claude
            response = call_claude_api(message)
        
        if not response:
            response = "申し訳ございません。現在AIサービスが利用できません。"
        
        return jsonify({
            'response': response,
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        app.logger.error(f"Chat API error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

def call_dify_api(message):
    """Call Dify API"""
    if not app.config.get('DIFY_API_KEY'):
        return None
    
    try:
        headers = {
            'Authorization': f"Bearer {app.config['DIFY_API_KEY']}",
            'Content-Type': 'application/json'
        }
        
        payload = {
            'inputs': {},
            'query': message,
            'response_mode': 'blocking',
            'user': 'web-user'
        }
        
        response = requests.post(
            f"{app.config['DIFY_API_BASE_URL']}/chat-messages",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('answer', '')
    
    except Exception as e:
        app.logger.error(f"Dify API error: {str(e)}")
    
    return None

def call_claude_api(message):
    """Call Claude API (Anthropic)"""
    if not app.config.get('ANTHROPIC_API_KEY'):
        return None
    
    try:
        headers = {
            'x-api-key': app.config['ANTHROPIC_API_KEY'],
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }
        
        payload = {
            'model': 'claude-3-opus-20240229',
            'messages': [
                {'role': 'user', 'content': message}
            ],
            'max_tokens': 1000,
            'temperature': 0.7
        }
        
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return data['content'][0]['text']
    
    except Exception as e:
        app.logger.error(f"Claude API error: {str(e)}")
    
    return None

# Chat interface template
CHAT_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>ベテランAI チャット</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 0;
            background: #f5f5f5;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .header {
            background: #1d4ed8;
            color: white;
            padding: 15px 20px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            max-width: 800px;
            width: 100%;
            margin: 0 auto;
        }
        .message {
            margin: 10px 0;
            display: flex;
            align-items: flex-start;
            animation: fadeIn 0.3s ease-in;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .message.user { justify-content: flex-end; }
        .message.assistant { justify-content: flex-start; }
        .message-content {
            max-width: 70%;
            padding: 10px 15px;
            border-radius: 18px;
            word-wrap: break-word;
        }
        .user .message-content {
            background: #1d4ed8;
            color: white;
            border-bottom-right-radius: 4px;
        }
        .assistant .message-content {
            background: white;
            color: #333;
            border: 1px solid #e0e0e0;
            border-bottom-left-radius: 4px;
        }
        .input-container {
            background: white;
            border-top: 1px solid #e0e0e0;
            padding: 15px;
            display: flex;
            gap: 10px;
            max-width: 800px;
            width: 100%;
            margin: 0 auto;
        }
        #messageInput {
            flex: 1;
            padding: 10px 15px;
            border: 1px solid #ddd;
            border-radius: 25px;
            outline: none;
            font-size: 16px;
        }
        #messageInput:focus {
            border-color: #1d4ed8;
        }
        #sendButton {
            background: #1d4ed8;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 16px;
            transition: background 0.2s;
        }
        #sendButton:hover {
            background: #1e40af;
        }
        #sendButton:disabled {
            background: #93bbf9;
            cursor: not-allowed;
        }
        .typing-indicator {
            display: none;
            padding: 10px 15px;
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 18px;
            border-bottom-left-radius: 4px;
            width: fit-content;
            margin: 10px 0;
        }
        .typing-indicator span {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #999;
            border-radius: 50%;
            margin: 0 2px;
            animation: typing 1.4s infinite;
        }
        .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
        .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typing {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-10px); }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 ベテランAI チャット</h1>
    </div>
    
    <div class="chat-container" id="chatContainer">
        <div class="message assistant">
            <div class="message-content">
                こんにちは！ベテランAIです。何かお手伝いできることはありますか？
            </div>
        </div>
    </div>
    
    <div class="typing-indicator" id="typingIndicator">
        <span></span>
        <span></span>
        <span></span>
    </div>
    
    <div class="input-container">
        <input 
            type="text" 
            id="messageInput" 
            placeholder="メッセージを入力..." 
            onkeypress="if(event.key==='Enter')sendMessage()"
        >
        <button id="sendButton" onclick="sendMessage()">送信</button>
    </div>
    
    <script>
        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            
            if (!message) return;
            
            // Add user message
            addMessage(message, 'user');
            
            // Clear input
            input.value = '';
            
            // Disable input
            input.disabled = true;
            document.getElementById('sendButton').disabled = true;
            
            // Show typing indicator
            document.getElementById('typingIndicator').style.display = 'block';
            
            // Send to API
            fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
            })
            .then(response => response.json())
            .then(data => {
                // Hide typing indicator
                document.getElementById('typingIndicator').style.display = 'none';
                
                // Add assistant message
                if (data.response) {
                    addMessage(data.response, 'assistant');
                } else if (data.error) {
                    addMessage('エラーが発生しました: ' + data.error, 'assistant');
                }
            })
            .catch(error => {
                // Hide typing indicator
                document.getElementById('typingIndicator').style.display = 'none';
                
                addMessage('通信エラーが発生しました。', 'assistant');
                console.error('Error:', error);
            })
            .finally(() => {
                // Re-enable input
                input.disabled = false;
                document.getElementById('sendButton').disabled = false;
                input.focus();
            });
        }
        
        function addMessage(text, type) {
            const chatContainer = document.getElementById('chatContainer');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${type}`;
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            contentDiv.textContent = text;
            
            messageDiv.appendChild(contentDiv);
            chatContainer.appendChild(messageDiv);
            
            // Scroll to bottom
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    </script>
</body>
</html>
'''