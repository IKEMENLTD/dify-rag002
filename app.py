# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import json
import re
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize Supabase client
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

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

def save_conversation(user_id, message, response, source='web'):
    """Save conversation to database"""
    if not supabase:
        return
    
    try:
        # Save to conversations table
        conversation_data = {
            'user_id': user_id or 'anonymous',
            'message': message,
            'response': response,
            'source': source,
            'created_at': datetime.utcnow().isoformat()
        }
        supabase.table('conversations').insert(conversation_data).execute()
    except Exception as e:
        print(f"Database error: {str(e)}")

def extract_keywords(text):
    """Extract key terms with importance weighting"""
    import re
    
    # Enhanced stop words
    stop_words = {
        'の', 'に', 'は', 'を', 'が', 'で', 'と', 'て', 'だ', 'である', 'です', 'ます',
        'から', 'まで', 'より', 'について', 'という', 'こと', 'もの', 'これ', 'それ',
        'あれ', 'どう', 'なぜ', 'いつ', 'どこ', 'だれ', 'なに', 'どの', 'どんな', 'する', 
        'した', 'して', 'される', 'できる', 'できた', 'ある', 'あった', 'なる', 'なった',
        'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
        'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has',
        'do', 'did', 'does', 'will', 'would', 'could', 'should', 'may', 'might'
    }
    
    # Extract words with context
    words = re.findall(r'[ぁ-んァ-ン一-龯a-zA-Z0-9]+', text)
    
    # Weight keywords by length and frequency
    keyword_counts = {}
    for word in words:
        if len(word) > 1 and word.lower() not in stop_words:
            keyword_counts[word] = keyword_counts.get(word, 0) + 1
    
    # Sort by importance: longer words and higher frequency first
    sorted_keywords = sorted(keyword_counts.items(), 
                           key=lambda x: (len(x[0]), x[1]), reverse=True)
    
    return [kw[0] for kw in sorted_keywords[:8]]  # Return top 8 weighted keywords

def search_related_conversations(user_id, current_message, limit=8):
    """Search with relevance scoring and smart deduplication"""
    if not supabase:
        return []
    
    try:
        keywords = extract_keywords(current_message)
        if not keywords:
            return []
        
        # Collect all matches with relevance scoring
        conversation_scores = {}
        
        for i, keyword in enumerate(keywords[:6]):  # Top 6 keywords
            try:
                # Single query searching both fields
                matches = supabase.table('conversations')\
                    .select('message, response, created_at')\
                    .eq('user_id', user_id or 'anonymous')\
                    .or_(f'message.ilike.%{keyword}%,response.ilike.%{keyword}%')\
                    .order('created_at', desc=True)\
                    .limit(20)\
                    .execute()
                
                # Score each conversation
                keyword_weight = 1.0 / (i + 1)  # Higher weight for earlier keywords
                
                for conv in matches.data:
                    conv_id = conv['created_at']
                    if conv_id not in conversation_scores:
                        conversation_scores[conv_id] = {
                            'conversation': conv,
                            'score': 0,
                            'matched_keywords': set()
                        }
                    
                    # Count keyword occurrences in both message and response
                    msg_count = conv['message'].lower().count(keyword.lower())
                    resp_count = conv['response'].lower().count(keyword.lower())
                    
                    # Add weighted score
                    conversation_scores[conv_id]['score'] += (msg_count + resp_count) * keyword_weight
                    conversation_scores[conv_id]['matched_keywords'].add(keyword)
                    
            except Exception as e:
                print(f"Keyword search error for '{keyword}': {str(e)}")
                continue
        
        # Sort by relevance score and return top conversations
        sorted_convs = sorted(conversation_scores.values(), 
                            key=lambda x: x['score'], reverse=True)
        
        return [item['conversation'] for item in sorted_convs[:limit]]
        
    except Exception as e:
        print(f"Related conversation search error: {str(e)}")
        return []

def get_conversation_history(user_id, limit=5):
    """Get recent conversation history for immediate context"""
    if not supabase:
        return []
    
    try:
        response = supabase.table('conversations')\
            .select('message, response, created_at')\
            .eq('user_id', user_id or 'anonymous')\
            .order('created_at', desc=True)\
            .limit(limit)\
            .execute()
        return response.data
    except Exception as e:
        print(f"Database error: {str(e)}")
        return []

def search_knowledge_base(query, limit=5):
    """Search knowledge base for relevant information using keywords"""
    if not supabase:
        return []
    
    try:
        keywords = extract_keywords(query)
        if not keywords:
            return []
        
        knowledge_results = []
        
        for keyword in keywords[:3]:  # Limit to top 3 keywords
            try:
                # Search in title and content
                title_matches = supabase.table('knowledge_base')\
                    .select('title, content, tags, created_at')\
                    .ilike('title', f'%{keyword}%')\
                    .limit(2)\
                    .execute()
                
                content_matches = supabase.table('knowledge_base')\
                    .select('title, content, tags, created_at')\
                    .ilike('content', f'%{keyword}%')\
                    .limit(2)\
                    .execute()
                
                knowledge_results.extend(title_matches.data)
                knowledge_results.extend(content_matches.data)
                
            except Exception as e:
                print(f"Knowledge search error for '{keyword}': {str(e)}")
                continue
        
        # Remove duplicates
        seen = set()
        unique_knowledge = []
        for kb in knowledge_results:
            key = f"{kb['title']}_{kb.get('created_at', '')}"
            if key not in seen:
                seen.add(key)
                unique_knowledge.append(kb)
        
        return unique_knowledge[:limit]
        
    except Exception as e:
        print(f"Knowledge base search error: {str(e)}")
        return []

def generate_context_aware_response(message, user_id='anonymous'):
    """Generate response with adaptive context weighting"""
    context_parts = []
    
    # 1. Get recent conversation history (immediate context)
    recent_history = get_conversation_history(user_id, 4)
    
    # 2. Search for related conversations with relevance scoring
    related_conversations = search_related_conversations(user_id, message, 6)
    
    # 3. Search knowledge base for relevant information
    knowledge = search_knowledge_base(message, 4)
    
    # Adaptive context building based on available data
    total_context_items = len(recent_history) + len(related_conversations) + len(knowledge)
    
    if recent_history:
        context_parts.append("【直近の対話履歴】")
        for i, conv in enumerate(reversed(recent_history)):
            # Show more detail for more recent conversations
            detail_length = 200 if i < 2 else 120
            context_parts.append(f"Q{i+1}: {conv['message']}")
            context_parts.append(f"A{i+1}: {conv['response'][:detail_length]}{'...' if len(conv['response']) > detail_length else ''}")
    
    if related_conversations:
        # Filter out recent conversations to avoid duplication
        recent_times = {conv['created_at'] for conv in recent_history} if recent_history else set()
        unique_related = [conv for conv in related_conversations 
                         if conv['created_at'] not in recent_times]
        
        if unique_related:
            context_parts.append("\n【関連する過去の経験】")
            for i, conv in enumerate(unique_related[:5]):  # Top 5 most relevant
                context_parts.append(f"関連事例{i+1}: {conv['message'][:80]}")
                context_parts.append(f"当時の対応: {conv['response'][:120]}...")
    
    if knowledge:
        context_parts.append("\n【蓄積された専門知識】")
        for i, kb in enumerate(knowledge):
            context_parts.append(f"知識{i+1}: {kb['title']}")
            context_parts.append(f"内容: {kb['content'][:180]}{'...' if len(kb['content']) > 180 else ''}")
    
    # Build enhanced message with adaptive prompting
    if context_parts:
        context = "\n".join(context_parts)
        context_strength = "豊富な" if total_context_items > 8 else "適切な" if total_context_items > 4 else "限定的な"
        
        enhanced_message = f"""あなたは経験豊富なベテランAIアドバイザーです。以下の{context_strength}過去データを活用して、継続性と専門性のある回答をしてください。

{context}

【現在の相談内容】
{message}

【回答指針】
1. 過去の対話パターンを踏まえた一貫性のある回答
2. 関連する過去事例があれば具体的に参照して説明
3. 蓄積された知識を実践的に活用
4. ベテランらしい深い洞察と具体的なアドバイス
5. 必要に応じて過去の成功/失敗パターンから学んだ教訓を含める"""
    else:
        enhanced_message = f"""あなたは経験豊富なベテランAIアドバイザーです。過去データは限られていますが、ベテランとしての知見を活かして的確なアドバイスをしてください。

【相談内容】
{message}

【回答方針】
- 一般的なベストプラクティスを踏まえた実践的なアドバイス
- 潜在的なリスクや注意点も含めた包括的な視点
- 具体的で行動につながる提案"""
    
    return enhanced_message

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
        user_id = data.get('user_id', 'anonymous')  # Allow user identification
        
        # Generate context-aware message using conversation history and knowledge base
        enhanced_message = generate_context_aware_response(message, user_id)
        
        # Default response
        response = f"受信しました: {message}"
        
        # Check environment variables
        dify_api_key = os.getenv('DIFY_API_KEY')
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        
        if not dify_api_key and not anthropic_key:
            response = "APIキーが設定されていません。環境変数を確認してください。"
        
        # Try Dify first with enhanced context
        if dify_api_key:
            try:
                headers = {
                    'Authorization': f'Bearer {dify_api_key}',
                    'Content-Type': 'application/json'
                }
                payload = {
                    'inputs': {},
                    'query': enhanced_message,  # Use enhanced message with context
                    'response_mode': 'blocking',
                    'conversation_id': '',
                    'user': user_id or 'web-user'
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
                        
                        # Save conversation to database for future context
                        save_conversation(user_id, message, response, 'web')
                        
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
        
        # Provide context information for UI
        context_info = []
        recent_count = len(get_conversation_history(user_id, 3))
        related_count = len(search_related_conversations(user_id, message, 5))
        knowledge_count = len(search_knowledge_base(message, 3))
        
        if recent_count > 0:
            context_info.append(f"直近{recent_count}件")
        if related_count > 0:
            context_info.append(f"関連{related_count}件") 
        if knowledge_count > 0:
            context_info.append(f"知識{knowledge_count}件")
        
        return jsonify({
            'response': response,
            'has_context': len(enhanced_message) > len(message),
            'context_info': "、".join(context_info) if context_info else None
        })
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
    """LINE webhook handler - collect and save LINE messages"""
    try:
        body = request.get_json()
        
        if not body or 'events' not in body:
            return 'OK', 200
        
        for event in body['events']:
            if event.get('type') == 'message' and event.get('message', {}).get('type') == 'text':
                message_text = event.get('message', {}).get('text', '')
                user_id = event.get('source', {}).get('userId', 'unknown')
                
                # Save all LINE messages to external_chat_logs for data collection
                if supabase:
                    try:
                        log_data = {
                            'source': 'line',
                            'user_id': user_id,
                            'message': message_text,
                            'timestamp': datetime.utcnow().isoformat(),
                            'metadata': json.dumps(event)
                        }
                        supabase.table('external_chat_logs').insert(log_data).execute()
                    except Exception as e:
                        print(f"Failed to save LINE message: {str(e)}")
                
                # Only respond if message contains "ベテランAI"
                if 'ベテランAI' in message_text:
                    # Remove "ベテランAI" from message for processing
                    clean_message = message_text.replace('ベテランAI', '').strip()
                    
                    # Process through our enhanced chat API
                    enhanced_message = generate_context_aware_response(clean_message, f"line_{user_id}")
                    
                    # Get AI response (simplified version of api_chat logic)
                    dify_api_key = os.getenv('DIFY_API_KEY')
                    if dify_api_key and clean_message:
                        try:
                            headers = {
                                'Authorization': f'Bearer {dify_api_key}',
                                'Content-Type': 'application/json'
                            }
                            payload = {
                                'inputs': {},
                                'query': enhanced_message,
                                'response_mode': 'blocking',
                                'conversation_id': '',
                                'user': f'line_{user_id}'
                            }
                            
                            resp = requests.post(
                                'https://api.dify.ai/v1/chat-messages',
                                headers=headers,
                                json=payload,
                                timeout=30
                            )
                            
                            if resp.status_code == 200:
                                data = resp.json()
                                response = clean_response(data.get('answer', ''))
                                
                                # Save LINE conversation
                                save_conversation(f"line_{user_id}", clean_message, response, 'line')
                                
                                # Here you would send the response back to LINE
                                # This requires LINE Bot SDK and proper setup
                                
                        except Exception as e:
                            print(f"Error processing LINE message: {str(e)}")
        
        return 'OK', 200
    except Exception as e:
        print(f"LINE webhook error: {str(e)}")
        return 'OK', 200

# New endpoints for data management
@app.route('/api/knowledge', methods=['POST'])
def add_knowledge():
    """Add information to knowledge base"""
    try:
        data = request.get_json()
        title = data.get('title', '')
        content = data.get('content', '')
        tags = data.get('tags', [])
        
        if not supabase:
            return jsonify({'error': 'Database not configured'}), 500
            
        knowledge_data = {
            'title': title,
            'content': content,
            'tags': tags,
            'created_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('knowledge_base').insert(knowledge_data).execute()
        return jsonify({'success': True, 'data': result.data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """Get conversation history"""
    try:
        user_id = request.args.get('user_id', 'anonymous')
        limit = int(request.args.get('limit', 50))
        
        if not supabase:
            return jsonify({'error': 'Database not configured'}), 500
            
        response = supabase.table('conversations')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('created_at', desc=True)\
            .limit(limit)\
            .execute()
            
        return jsonify({'conversations': response.data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tldv-webhook', methods=['POST'])
def tldv_webhook():
    """tl:dv webhook to receive meeting data"""
    try:
        data = request.get_json()
        
        if not supabase:
            return jsonify({'error': 'Database not configured'}), 500
        
        # Extract meeting information
        meeting_data = {
            'meeting_id': data.get('meeting_id'),
            'title': data.get('title', ''),
            'transcript': data.get('transcript', ''),
            'summary': data.get('summary', ''),
            'participants': data.get('participants', []),
            'duration': data.get('duration', 0),
            'date': data.get('date', datetime.utcnow().isoformat()),
            'metadata': json.dumps(data)
        }
        
        # Save to external_chat_logs with tldv source
        log_data = {
            'source': 'tldv',
            'user_id': 'system',
            'message': f"Meeting: {meeting_data['title']}",
            'timestamp': meeting_data['date'],
            'metadata': meeting_data['metadata']
        }
        
        supabase.table('external_chat_logs').insert(log_data).execute()
        
        # Also add key insights to knowledge base
        if meeting_data['summary']:
            knowledge_data = {
                'title': f"会議: {meeting_data['title']}",
                'content': f"概要: {meeting_data['summary']}\n\n詳細: {meeting_data['transcript'][:500]}...",
                'tags': ['meeting', 'tldv'],
                'created_at': meeting_data['date']
            }
            supabase.table('knowledge_base').insert(knowledge_data).execute()
        
        return jsonify({'success': True, 'message': 'Meeting data saved'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/import-data', methods=['POST'])
def import_external_data():
    """Import data from various sources manually"""
    try:
        data = request.get_json()
        source = data.get('source', 'manual')
        content_type = data.get('type', 'text')
        content = data.get('content', '')
        title = data.get('title', f'{source}からのインポート')
        
        if not supabase:
            return jsonify({'error': 'Database not configured'}), 500
        
        # Save to knowledge base
        knowledge_data = {
            'title': title,
            'content': content,
            'tags': [source, content_type],
            'created_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('knowledge_base').insert(knowledge_data).execute()
        
        # Also log the import
        log_data = {
            'source': source,
            'user_id': 'system',
            'message': f"データインポート: {title}",
            'timestamp': datetime.utcnow().isoformat(),
            'metadata': json.dumps({'type': content_type, 'length': len(content)})
        }
        
        supabase.table('external_chat_logs').insert(log_data).execute()
        
        return jsonify({'success': True, 'data': result.data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)