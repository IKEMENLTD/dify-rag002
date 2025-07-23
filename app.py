# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from functools import wraps
import hmac
import hashlib
import secrets
import logging
import base64
from auth_system import AuthManager, require_auth, require_line_auth
from share_system import create_conversation_share_link, verify_share_token, get_related_conversations, SHARED_CONVERSATION_TEMPLATE
from datetime import datetime
from flask import render_template_string
import os
import requests
import json
import re
from datetime import datetime, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
import pytz
import dateutil.parser

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Security configurations
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
CORS(app, origins=os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000').split(','))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security headers
@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response

# Initialize Supabase client
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

# Initialize LINE Bot API
line_bot_api = None
line_handler = None
line_access_token = os.getenv('LINE_ACCESS_TOKEN')
line_secret = os.getenv('LINE_SECRET')

if line_access_token and line_secret:
    line_bot_api = LineBotApi(line_access_token)
    line_handler = WebhookHandler(line_secret)

# Initialize scheduler for reminders
scheduler = BackgroundScheduler()
scheduler.start()

# Cleanup on exit
import atexit
atexit.register(lambda: scheduler.shutdown())

# Initialize Authentication Manager
@app.before_request
def load_auth_manager():
    """Load authentication manager for each request"""
    g.auth_manager = AuthManager(supabase)

def validate_input(text, max_length=1000):
    """Validate and sanitize user input"""
    if not text or not isinstance(text, str):
        return None
    
    # Remove potential XSS
    text = text.replace('<', '&lt;').replace('>', '&gt;')
    text = text.replace('javascript:', '').replace('data:', '')
    
    # Limit length
    if len(text) > max_length:
        text = text[:max_length]
    
    return text.strip()

def validate_user_id(user_id):
    """Validate user ID format"""
    if not user_id or not isinstance(user_id, str):
        return False
    
    # Allow alphanumeric, underscore, hyphen
    import string
    allowed_chars = string.ascii_letters + string.digits + '_-'
    if not all(c in allowed_chars for c in user_id):
        return False
    
    return len(user_id) <= 100

def verify_line_signature(request):
    """Verify LINE webhook signature"""
    channel_secret = os.getenv('LINE_SECRET', '')
    if not channel_secret:
        return False
    
    body = request.get_data(as_text=True)
    signature = request.headers.get('X-Line-Signature')
    
    if not signature:
        return False
    
    # LINE uses base64 encoded HMAC-SHA256
    hash_value = hmac.new(
        channel_secret.encode('utf-8'),
        body.encode('utf-8'),
        hashlib.sha256
    ).digest()
    
    expected_signature = base64.b64encode(hash_value).decode()
    
    return hmac.compare_digest(signature, expected_signature)

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
        
        # Validate user_id to prevent injection
        if not user_id or not isinstance(user_id, str) or len(user_id) > 100:
            return []
        
        # Collect all matches with relevance scoring
        conversation_scores = {}
        
        for i, keyword in enumerate(keywords[:6]):  # Top 6 keywords
            try:
                # Sanitize keyword to prevent injection
                keyword = str(keyword).replace('%', '').replace('_', '').replace("'", '').replace('"', '')[:50]
                if not keyword:
                    continue
                
                # Safe parameterized query
                matches = supabase.table('conversations')\
                    .select('message, response, created_at')\
                    .eq('user_id', user_id)\
                    .ilike('message', f'%{keyword}%')\
                    .order('created_at', desc=True)\
                    .limit(10)\
                    .execute()
                    
                response_matches = supabase.table('conversations')\
                    .select('message, response, created_at')\
                    .eq('user_id', user_id)\
                    .ilike('response', f'%{keyword}%')\
                    .order('created_at', desc=True)\
                    .limit(10)\
                    .execute()
                
                # Score each conversation
                keyword_weight = 1.0 / (i + 1)  # Higher weight for earlier keywords
                
                all_matches = matches.data + response_matches.data
                for conv in all_matches:
                    conv_id = conv['created_at']
                    if conv_id not in conversation_scores:
                        conversation_scores[conv_id] = {
                            'conversation': conv,
                            'score': 0,
                            'matched_keywords': set()
                        }
                    
                    # Count keyword occurrences safely
                    msg_count = str(conv.get('message', '')).lower().count(keyword.lower())
                    resp_count = str(conv.get('response', '')).lower().count(keyword.lower())
                    
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

def parse_reminder_message(text):
    """Parse reminder message like リマインくん"""
    import re
    
    # Remove "リマインダー" trigger word
    text = text.replace('リマインダー', '').strip()
    
    # Patterns for different time formats
    patterns = [
        # 毎日 HH:MM format
        r'毎日\s*(\d{1,2}):(\d{2})\s*(.+)',
        # 毎日 HH時MM分 format  
        r'毎日\s*(\d{1,2})時(\d{1,2})分\s*(.+)',
        # YYYY/MM/DD HH:MM format
        r'(\d{4})/(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})\s*(.+)',
        # MM/DD HH:MM format (this year)
        r'(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})\s*(.+)',
        # X日後 HH:MM format
        r'(\d+)日後\s*(\d{1,2}):(\d{2})\s*(.+)',
        # Tomorrow HH:MM
        r'明日\s*(\d{1,2}):(\d{2})\s*(.+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            
            if '毎日' in pattern:
                if ':' in pattern:
                    # 毎日 HH:MM
                    hour, minute, content = groups
                    return {
                        'type': 'daily',
                        'hour': int(hour),
                        'minute': int(minute),
                        'content': content.strip()
                    }
                else:
                    # 毎日 HH時MM分
                    hour, minute, content = groups
                    return {
                        'type': 'daily',
                        'hour': int(hour),
                        'minute': int(minute),
                        'content': content.strip()
                    }
            
            elif '/' in pattern and len(groups) == 6:
                # YYYY/MM/DD HH:MM
                year, month, day, hour, minute, content = groups
                return {
                    'type': 'once',
                    'datetime': f"{year}-{month.zfill(2)}-{day.zfill(2)} {hour.zfill(2)}:{minute}:00",
                    'content': content.strip()
                }
            
            elif '/' in pattern and len(groups) == 5:
                # MM/DD HH:MM (this year)
                month, day, hour, minute, content = groups
                current_year = datetime.now().year
                return {
                    'type': 'once',
                    'datetime': f"{current_year}-{month.zfill(2)}-{day.zfill(2)} {hour.zfill(2)}:{minute}:00",
                    'content': content.strip()
                }
            
            elif '日後' in pattern:
                # X日後 HH:MM
                days, hour, minute, content = groups
                target_date = datetime.now() + timedelta(days=int(days))
                return {
                    'type': 'once',
                    'datetime': f"{target_date.strftime('%Y-%m-%d')} {hour.zfill(2)}:{minute}:00",
                    'content': content.strip()
                }
            
            elif '明日' in pattern:
                # 明日 HH:MM
                hour, minute, content = groups
                tomorrow = datetime.now() + timedelta(days=1)
                return {
                    'type': 'once',
                    'datetime': f"{tomorrow.strftime('%Y-%m-%d')} {hour.zfill(2)}:{minute}:00",
                    'content': content.strip()
                }
    
    return None

def save_reminder(user_id, reminder_data, source='line'):
    """Save reminder to database"""
    if not supabase:
        return None
    
    try:
        reminder_record = {
            'user_id': user_id,
            'content': reminder_data['content'],
            'reminder_type': reminder_data['type'],
            'scheduled_time': reminder_data.get('datetime'),
            'hour': reminder_data.get('hour'),
            'minute': reminder_data.get('minute'),
            'source': source,
            'is_active': True,
            'created_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('reminders').insert(reminder_record).execute()
        return result.data[0] if result.data else None
        
    except Exception as e:
        print(f"Failed to save reminder: {str(e)}")
        return None

def schedule_reminder(reminder_id, reminder_data, user_id):
    """Schedule reminder using APScheduler"""
    try:
        jst = pytz.timezone('Asia/Tokyo')
        
        if reminder_data['type'] == 'daily':
            # Daily recurring reminder
            trigger = CronTrigger(
                hour=reminder_data['hour'],
                minute=reminder_data['minute'],
                timezone=jst
            )
            job_id = f"daily_{reminder_id}"
            
        elif reminder_data['type'] == 'once':
            # One-time reminder
            reminder_time = datetime.fromisoformat(reminder_data['datetime'])
            reminder_time = jst.localize(reminder_time)
            
            trigger = DateTrigger(run_date=reminder_time)
            job_id = f"once_{reminder_id}"
        
        else:
            return False
        
        # Add job to scheduler
        scheduler.add_job(
            func=send_reminder,
            trigger=trigger,
            id=job_id,
            args=[user_id, reminder_data['content'], reminder_id],
            replace_existing=True
        )
        
        return True
        
    except Exception as e:
        print(f"Failed to schedule reminder: {str(e)}")
        return False

def send_reminder(user_id, content, reminder_id):
    """Send reminder message to user"""
    try:
        if line_bot_api and user_id.startswith('line_'):
            # Extract actual LINE user ID
            actual_user_id = user_id.replace('line_', '')
            
            reminder_message = f"🔔 リマインダー\n\n{content}\n\n⏰ {datetime.now().strftime('%Y/%m/%d %H:%M')}"
            
            # Send push message to user
            line_bot_api.push_message(
                actual_user_id,
                TextSendMessage(text=reminder_message)
            )
            
            print(f"Reminder sent to {user_id}: {content}")
            
            # Mark one-time reminders as completed
            if reminder_id and supabase:
                try:
                    supabase.table('reminders')\
                        .update({'is_active': False, 'completed_at': datetime.utcnow().isoformat()})\
                        .eq('id', reminder_id)\
                        .execute()
                except Exception as e:
                    print(f"Failed to update reminder status: {str(e)}")
        
    except Exception as e:
        print(f"Failed to send reminder: {str(e)}")

def process_reminder_request(message_text, user_id):
    """Process reminder request and return response"""
    reminder_data = parse_reminder_message(message_text)
    
    if not reminder_data:
        return "❌ リマインダーの形式を認識できませんでした。\n\n例:\n・毎日 9:00 薬を飲む\n・12/25 14:30 会議の準備\n・明日 10:00 買い物\n・3日後 15:00 プレゼント準備"
    
    # Save to database
    saved_reminder = save_reminder(user_id, reminder_data)
    if not saved_reminder:
        return "❌ リマインダーの保存に失敗しました。"
    
    # Schedule the reminder
    success = schedule_reminder(saved_reminder['id'], reminder_data, user_id)
    if not success:
        return "❌ リマインダーのスケジュール設定に失敗しました。"
    
    # Generate response message
    if reminder_data['type'] == 'daily':
        return f"✅ 毎日のリマインダーを設定しました！\n\n📝 内容: {reminder_data['content']}\n⏰ 時刻: 毎日 {reminder_data['hour']:02d}:{reminder_data['minute']:02d}"
    else:
        return f"✅ リマインダーを設定しました！\n\n📝 内容: {reminder_data['content']}\n⏰ 日時: {reminder_data['datetime'].replace('-', '/').replace(' ', ' ')}"

@app.route('/')
def home():
    """認証付きメインページ"""
    try:
        with open('frontend_auth.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
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
                <p>⚠️ 認証システムを有効にするには frontend_auth.html が必要です</p>
            </div>
            <p><a href="/ping">Ping Test</a></p>
            <p><a href="/chat">チャット</a></p>
            <p><a href="/api/status">API Status</a></p>
        </body>
        </html>
        """

# === 認証エンドポイント ===

@app.route('/api/auth/login', methods=['POST'])
def login():
    """ユーザーログイン"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        email = validate_input(data.get('email', ''), max_length=255)
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        result = g.auth_manager.authenticate_user(email, password)
        
        if result['success']:
            return jsonify({
                'token': result['token'],
                'user': result['user'],
                'refresh_token': result.get('refresh_token')
            })
        else:
            return jsonify({'error': result['error']}), 401
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/api/auth/register', methods=['POST'])
def register():
    """新規ユーザー登録"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        email = validate_input(data.get('email', ''), max_length=255)
        password = data.get('password', '')
        display_name = validate_input(data.get('display_name', ''), max_length=100)
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        try:
            # Supabase Auth登録
            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            
            if auth_response.user:
                # ユーザープロファイル作成
                user_data = {
                    'auth_user_id': auth_response.user.id,
                    'email': email,
                    'display_name': display_name or email.split('@')[0],
                    'role': 'user',
                    'auth_provider': 'email',
                    'created_at': datetime.utcnow().isoformat()
                }
                
                supabase.table('users').insert(user_data).execute()
                
                return jsonify({
                    'message': 'Registration successful. Please check your email for verification.',
                    'user_id': auth_response.user.id
                })
            else:
                return jsonify({'error': 'Registration failed'}), 400
                
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return jsonify({'error': 'Registration failed. Email may already exist.'}), 400
                
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/api/auth/profile', methods=['GET'])
@require_auth()
def get_profile():
    """ユーザープロファイル取得"""
    try:
        user_data = supabase.table('users')\
            .select('id, email, display_name, role, created_at, line_id, auth_provider')\
            .eq('id', g.current_user_id)\
            .single()\
            .execute()
        
        return jsonify({
            'user': user_data.data,
            'permissions': g.user_permissions
        })
    except Exception as e:
        logger.error(f"Profile error: {str(e)}")
        return jsonify({'error': 'Failed to get profile'}), 500

@app.route('/api/auth/api-keys', methods=['POST'])
@require_auth(['write'])
def create_api_key():
    """API Key生成"""
    try:
        data = request.get_json()
        name = validate_input(data.get('name', 'Default API Key'), max_length=100)
        permissions = data.get('permissions', ['read'])
        
        # 権限検証
        valid_permissions = ['read', 'write', 'delete']
        permissions = [p for p in permissions if p in valid_permissions]
        
        if not permissions:
            permissions = ['read']
        
        api_key = g.auth_manager.create_api_key(g.current_user_id, name, permissions)
        
        return jsonify({
            'api_key': api_key,
            'name': name,
            'permissions': permissions,
            'note': 'このキーは再表示されません。安全に保管してください。'
        })
        
    except Exception as e:
        logger.error(f"API key creation error: {str(e)}")
        return jsonify({'error': 'Failed to create API key'}), 500

@app.route('/api/auth/logout', methods=['POST'])
@require_auth()
def logout():
    """ログアウト"""
    try:
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            payload = g.auth_manager.verify_jwt_token(token)
            if payload:
                g.auth_manager.revoke_token(payload.get('jti'))
        
        return jsonify({'message': 'Logged out successfully'})
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({'message': 'Logged out'})

# === 会話共有システム ===

@app.route('/api/conversations/<conversation_id>/share', methods=['POST'])
@require_auth(['write'])
def create_share_link(conversation_id):
    """会話共有リンク生成"""
    try:
        data = request.get_json() or {}
        expires_hours = data.get('expires_hours', 24)  # デフォルト24時間
        password = data.get('password')  # オプション
        permissions = data.get('permissions', ['read'])  # read, comment
        
        result = create_conversation_share_link(
            supabase, conversation_id, g.current_user_id, 
            expires_hours, password, permissions
        )
        
        if 'error' in result:
            return jsonify(result), 404
        
        share_url = f"{request.host_url}share/{result['share_token']}"
        
        return jsonify({
            'success': True,
            'share_url': share_url,
            'expires_at': result['expires_at'],
            'permissions': permissions
        })
        
    except Exception as e:
        logger.error(f"Share link creation error: {str(e)}")
        return jsonify({'error': f'共有リンク生成エラー: {str(e)}'}), 500

@app.route('/share/<share_token>', methods=['GET'])
def view_shared_conversation(share_token):
    """共有会話表示（HTML）"""
    try:
        password = request.args.get('password')
        result = verify_share_token(supabase, share_token, password)
        
        if 'error' in result:
            if result.get('require_password'):
                return render_template_string(SHARED_CONVERSATION_TEMPLATE, 
                                            require_password=True)
            return f"エラー: {result['error']}", 404 if 'invalid' in result['error'].lower() else 410
        
        conversation = result['conversation']
        related_conversations = get_related_conversations(
            supabase, conversation['user_uuid'], conversation['id']
        )
        
        return render_template_string(SHARED_CONVERSATION_TEMPLATE,
            conversation=conversation,
            related_conversations=related_conversations,
            expires_at=result['expires_at'],
            require_password=False
        )
        
    except Exception as e:
        logger.error(f"Shared conversation view error: {str(e)}")
        return f"エラー: {str(e)}", 500

@app.route('/api/share/<share_token>', methods=['GET'])
def get_shared_conversation_api(share_token):
    """共有会話取得（JSON API）"""
    try:
        password = request.args.get('password')
        result = verify_share_token(supabase, share_token, password)
        
        if 'error' in result:
            status_code = 404 if 'invalid' in result['error'].lower() else 410
            return jsonify(result), status_code
        
        # 関連会話も含めて返却
        related_conversations = get_related_conversations(
            supabase, result['conversation']['user_uuid'], result['conversation']['id']
        )
        
        return jsonify({
            'success': True,
            'conversation': result['conversation'],
            'related_conversations': related_conversations,
            'permissions': result['permissions'],
            'expires_at': result['expires_at']
        })
        
    except Exception as e:
        logger.error(f"Shared conversation API error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/conversations/<conversation_id>/shares', methods=['GET'])
@require_auth(['read'])
def list_conversation_shares(conversation_id):
    """会話の共有リンク一覧"""
    try:
        shares = supabase.table('shared_conversations')\
            .select('id, share_token, expires_at, permissions, is_active, access_count, created_at')\
            .eq('conversation_id', conversation_id)\
            .eq('created_by', g.current_user_id)\
            .order('created_at', desc=True)\
            .execute()
        
        return jsonify({
            'success': True,
            'shares': shares.data
        })
        
    except Exception as e:
        logger.error(f"List shares error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/shares/<share_token>/revoke', methods=['DELETE'])
@require_auth(['write'])
def revoke_share_link(share_token):
    """共有リンク無効化"""
    try:
        result = supabase.table('shared_conversations')\
            .update({'is_active': False})\
            .eq('share_token', share_token)\
            .eq('created_by', g.current_user_id)\
            .execute()
        
        return jsonify({
            'success': True,
            'message': '共有リンクを無効化しました'
        })
        
    except Exception as e:
        logger.error(f"Revoke share error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/manual')
@app.route('/user_manual.html')
def user_manual():
    """ユーザーマニュアルページ"""
    try:
        with open('user_manual.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "マニュアルファイルが見つかりません", 404

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
@require_auth(['write'])
def api_chat():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        message = validate_input(data.get('message', ''), max_length=2000)
        user_id = str(g.current_user_id)  # 認証済みユーザーIDを使用
        
        if not message:
            return jsonify({'error': 'Message is required and must be valid text'}), 400
        
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
@require_line_auth
def line_webhook():
    """LINE webhook handler - collect and save LINE messages"""
    try:
        
        body = request.get_json()
        
        if not body or 'events' not in body:
            return 'OK', 200
        
        for event in body['events']:
            if event.get('type') == 'message' and event.get('message', {}).get('type') == 'text':
                message_text = validate_input(event.get('message', {}).get('text', ''), max_length=2000)
                user_id = event.get('source', {}).get('userId', 'unknown')
                
                # Skip if message is invalid
                if not message_text or not validate_user_id(user_id):
                    continue
                
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
                
                # Process different types of messages
                reply_text = None
                
                # Check for reminder requests
                if 'リマインダー' in message_text:
                    reply_text = process_reminder_request(message_text, f"line_{user_id}")
                
                # Check for AI chat requests
                elif 'ベテランAI' in message_text:
                    # Remove "ベテランAI" from message for processing
                    clean_message = message_text.replace('ベテランAI', '').strip()
                    
                    # Process through our enhanced chat API
                    enhanced_message = generate_context_aware_response(clean_message, f"line_{user_id}")
                    
                    # Get AI response
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
                                reply_text = clean_response(data.get('answer', ''))
                                
                                # Save LINE conversation
                                save_conversation(f"line_{user_id}", clean_message, reply_text, 'line')
                                
                        except Exception as e:
                            reply_text = f"エラーが発生しました: {str(e)[:50]}"
                            print(f"Error processing LINE message: {str(e)}")
                
                # Send reply if we have a response
                if reply_text and line_bot_api:
                    try:
                        line_bot_api.reply_message(
                            event.get('replyToken'),
                            TextSendMessage(text=reply_text)
                        )
                    except Exception as e:
                        print(f"Failed to send LINE reply: {str(e)}")
        
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

@app.route('/api/reminder', methods=['POST'])
@require_auth(['write'])
def create_reminder():
    """Create a new reminder"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
            
        message = validate_input(data.get('message', ''), max_length=500)
        user_id = str(g.current_user_id)  # 認証済みユーザーIDを使用
        
        if not message:
            return jsonify({'error': 'Message is required and must be valid text'}), 400
        
        # Process reminder request
        response = process_reminder_request(f"リマインダー {message}", user_id)
        
        return jsonify({
            'success': True,
            'response': response
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reminders', methods=['GET'])
@require_auth(['read'])
def get_user_reminders():
    """Get user's active reminders"""
    try:
        user_id = str(g.current_user_id)  # 認証済みユーザーIDを使用
        
        if not supabase:
            return jsonify({'error': 'Database not configured'}), 500
        
        response = supabase.table('reminders')\
            .select('id, content, reminder_type, scheduled_time, hour, minute, created_at')\
            .eq('user_id', user_id)\
            .eq('is_active', True)\
            .order('created_at', desc=True)\
            .limit(100)\
            .execute()
        
        return jsonify({'reminders': response.data})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reminder/<int:reminder_id>', methods=['DELETE'])
@require_auth(['delete'])
def delete_reminder(reminder_id):
    """Delete/deactivate a reminder"""
    try:
        user_id = str(g.current_user_id)  # 認証済みユーザーIDを使用
            
        if not supabase:
            return jsonify({'error': 'Database not configured'}), 500
        
        # First verify the reminder belongs to this user
        reminder = supabase.table('reminders')\
            .select('user_id')\
            .eq('id', reminder_id)\
            .single()\
            .execute()
            
        if not reminder.data or reminder.data.get('user_id') != user_id:
            return jsonify({'error': 'Reminder not found or unauthorized'}), 404
        
        # Deactivate reminder in database
        supabase.table('reminders')\
            .update({'is_active': False})\
            .eq('id', reminder_id)\
            .eq('user_id', user_id)\
            .execute()
        
        # Remove from scheduler
        try:
            scheduler.remove_job(f"daily_{reminder_id}")
        except:
            pass
        try:
            scheduler.remove_job(f"once_{reminder_id}")
        except:
            pass
        
        return jsonify({'success': True, 'message': 'Reminder deleted'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)