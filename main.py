import os
import json
import re
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import logging
from functools import wraps
import time
# hashlibとhmacは将来のセキュリティ機能のために保持
# 未使用のインポートを削除

# LINE SDK
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# Supabase SDK
from supabase import create_client, Client

# スケジューラー
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# =================================================================
# 1. 初期設定
# =================================================================
# ログ設定
log_level = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16777216))

# 本番環境でのセキュリティ設定
if os.getenv('FLASK_ENV') == 'production':
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# CORS設定
allowed_origins = os.getenv('ALLOWED_ORIGINS', '*').split(',')
CORS(app, origins=allowed_origins)

# =================================================================
# 2. 環境変数とAPIクライアントの読み込み
# =================================================================

# DIFY関連設定
DIFY_API_KEY = os.getenv('DIFY_API_KEY')
DIFY_API_URL = os.getenv('DIFY_API_URL', 'https://api.dify.ai/v1')
USE_DIFY_API = os.getenv('USE_DIFY_API', 'True').lower() == 'true'

# Claude API設定（Anthropic）
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

# API使用設定のログ出力
if DIFY_API_KEY and USE_DIFY_API:
    logger.info("Dify APIが有効化されています。Dify APIを優先的に使用します。")
elif ANTHROPIC_API_KEY:
    logger.info("Claude APIが使用されます。")
else:
    logger.warning("AIAPIキーが設定されていません。")
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    logger.error("SECRET_KEYが設定されていません。本番環境では必須です。")
    if os.getenv('FLASK_ENV') == 'production':
        raise ValueError("Production環境ではSECRET_KEYが必須です")
    SECRET_KEY = 'dev-only-key-change-in-production'  # 開発用のみ

# LINE設定
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')

# Chatwork設定
CHATWORK_WEBHOOK_TOKEN = os.getenv('CHATWORK_WEBHOOK_TOKEN')
CHATWORK_API_TOKEN = os.getenv('CHATWORK_API_TOKEN')

# 究極検索関連設定（環境変数があるが機能未実装）
ULTIMATE_SEARCH_ENABLED = os.getenv('ULTIMATE_SEARCH_ENABLED', 'False').lower() == 'true'
SEARCH_ANALYTICS_ENABLED = os.getenv('SEARCH_ANALYTICS_ENABLED', 'False').lower() == 'true'
SEMANTIC_SEARCH_THRESHOLD = float(os.getenv('SEMANTIC_SEARCH_THRESHOLD', '0.1'))
NGRAM_MIN_LENGTH = int(os.getenv('NGRAM_MIN_LENGTH', '2'))
NGRAM_MAX_LENGTH = int(os.getenv('NGRAM_MAX_LENGTH', '4'))
MAX_DOCUMENTS_FOR_ML = int(os.getenv('MAX_DOCUMENTS_FOR_ML', '1000'))
SEARCH_RESULT_CACHE_SIZE = int(os.getenv('SEARCH_RESULT_CACHE_SIZE', '100'))

# 究極検索機能の警告
if ULTIMATE_SEARCH_ENABLED:
    logger.warning("究極検索機能が有効化されていますが、現在未実装です。")

# Supabase設定
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
SUPABASE_BUCKET_NAME = os.getenv('SUPABASE_BUCKET_NAME', 'chat-uploads')

# Claude API設定確認
if not ANTHROPIC_API_KEY:
    logger.warning("ANTHROPIC_API_KEYが設定されていません。AI機能が制限されます。")

# APIクライアント初期化
line_bot_api = None
line_handler = None
supabase_client = None

# スケジューラー初期化
scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Tokyo'))

if LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET:
    line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
    line_handler = WebhookHandler(LINE_CHANNEL_SECRET)

if SUPABASE_URL and SUPABASE_KEY:
    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =================================================================
# 3. データベース初期化
# =================================================================
def init_database():
    """Supabaseテーブルの存在確認（テーブルは事前に作成済み想定）"""
    try:
        if not supabase_client:
            logger.warning("Supabase接続に失敗しました")
            return False
            
        # 基本的な接続テスト
        result = supabase_client.table('conversations').select('*', count='exact').limit(1).execute()
        logger.info("Supabaseデータベース接続確認完了")
        return True
        
    except Exception as e:
        logger.error(f"データベース初期化エラー: {e}")
        return False

# =================================================================
# 4. ヘルパー関数
# =================================================================
def get_supabase_client():
    """Supabaseクライアントを取得"""
    try:
        if not supabase_client:
            logger.error("Supabaseクライアントが初期化されていません")
            return None
        return supabase_client
    except Exception as e:
        logger.error(f"Supabaseクライアント取得エラー: {e}")
        return None


def call_dify_api(user_message, context_data=None, user_id=None):
    """Dify APIを呼び出してAI回答を生成"""
    try:
        if not DIFY_API_KEY or not DIFY_API_URL:
            logger.error("Dify APIの設定が不完全です")
            return None
            
        headers = {
            'Authorization': f'Bearer {DIFY_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        # 文脈情報をフォーマット
        context_text = ""
        if context_data:
            context_text = "\n\n【過去の会話から見つかった関連情報】\n"
            for i, item in enumerate(context_data, 1):
                created_at = item.get('created_at', 'Unknown')
                if hasattr(created_at, 'strftime'):
                    date_str = created_at.strftime('%Y-%m-%d %H:%M')
                else:
                    date_str = str(created_at)[:16]
                
                user_msg = item.get('user_message', '') or ''
                ai_resp = item.get('ai_response', '') or ''
                
                context_text += f"【情報{i}】({date_str})\n"
                context_text += f"質問: {user_msg[:150]}...\n"
                context_text += f"内容: {ai_resp[:300]}...\n\n"
        
        # Dify APIリクエストペイロード
        payload = {
            "inputs": {
                "query": user_message,
                "context": context_text
            },
            "query": user_message + context_text,
            "response_mode": "blocking",
            "conversation_id": "",
            "user": user_id or "default_user"
        }
        
        # Dify APIエンドポイント（チャット完了API）
        api_endpoint = f"{DIFY_API_URL}/chat-messages"
        
        response = requests.post(
            api_endpoint,
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info("Dify API呼び出し成功")
            return result.get('answer', result.get('data', {}).get('answer', ''))
        else:
            logger.error(f"Dify API エラー: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Dify API呼び出しエラー: {e}")
        return None

def extract_keywords_with_dify_api(message):
    """Dify APIを使ってキーワードを抽出"""
    try:
        if not DIFY_API_KEY or not DIFY_API_URL:
            return extract_keywords_fallback(message)
            
        headers = {
            'Authorization': f'Bearer {DIFY_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        keyword_prompt = f"""
以下のメッセージから重要なキーワードを3-5個抽出してください。
検索に使用するキーワードとして適切なものを選んでください。

メッセージ: {message}

抽出したキーワードをカンマ区切りで返してください。
例: キーワード1, キーワード2, キーワード3
"""
        
        payload = {
            "inputs": {"query": keyword_prompt},
            "query": keyword_prompt,
            "response_mode": "blocking",
            "conversation_id": "",
            "user": "keyword_extractor"
        }
        
        api_endpoint = f"{DIFY_API_URL}/chat-messages"
        
        response = requests.post(
            api_endpoint,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get('answer', result.get('data', {}).get('answer', ''))
            
            # カンマ区切りのキーワードを分割
            keywords = [k.strip() for k in answer.split(',') if k.strip()]
            logger.info(f"Dify APIキーワード抽出成功: {len(keywords)}個のキーワード")
            return keywords[:5]  # 最大5個
        else:
            logger.warning(f"Dify APIキーワード抽出失敗: {response.status_code}")
            return extract_keywords_fallback(message)
            
    except Exception as e:
        logger.error(f"Dify APIキーワード抽出エラー: {e}")
        return extract_keywords_fallback(message)

def extract_keywords_with_ai(message):
    """AIを使ってメッセージからキーワードを抽出（Dify優先、Claude APIフォールバック）"""
    try:
        # Dify APIを優先的に使用
        if DIFY_API_KEY and USE_DIFY_API:
            keywords = extract_keywords_with_dify_api(message)
            if keywords and len(keywords) > 0:
                return keywords
            logger.warning("Dify APIキーワード抽出に失敗、Claude APIにフォールバック")
        
        # Claude APIフォールバック
        if not ANTHROPIC_API_KEY:
            return extract_keywords_fallback(message)
            
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01'
        }
        
        prompt = f"""
以下のユーザーメッセージから、データベース検索に使用するキーワードを抽出してください。
重要な単語、固有名詞、技術用語、製品名、会社名などを重視してください。

ユーザーメッセージ: {message}

抽出したキーワードをJSON形式で返してください。例：
{{"keywords": ["キーワード1", "キーワード2", "キーワード3"]}}

レスポンスはJSONのみで、説明文は不要です。
"""

        # 実際に利用可能なClaudeモデルを順に試行
        models_to_try = [
            "claude-3-5-sonnet-20241022",   # Claude 3.5 Sonnet (最新安定版)
            "claude-3-5-haiku-20241022",    # Claude 3.5 Haiku (高速)
            "claude-3-opus-20240229"        # Claude 3 Opus (高性能)
        ]
        
        for model in models_to_try:
            try:
                data = {
                    "model": model,
                    "max_tokens": 300,
                    "temperature": 0.1,  # 一貫性重視
                    "messages": [
                        {
                            "role": "user", 
                            "content": prompt
                        }
                    ]
                }
                
                response = requests.post(
                    'https://api.anthropic.com/v1/messages',
                    headers=headers,
                    json=data,
                    timeout=15
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result['content'][0]['text']
                    
                    # JSONを抽出
                    try:
                        keywords_data = json.loads(content)
                        logger.info(f"キーワード抽出成功 (モデル: {model})")
                        return keywords_data.get('keywords', [])
                    except json.JSONDecodeError:
                        # JSONパースに失敗した場合、正規表現でキーワードを抽出
                        matches = re.findall(r'"([^"]+)"', content)
                        return matches[:5]  # 最大5個
                elif response.status_code == 404:
                    # モデルが見つからない場合、次のモデルを試行
                    logger.warning(f"モデル {model} が利用できません。次のモデルを試行中...")
                    continue
                else:
                    logger.warning(f"Claude API エラー: {response.status_code} (モデル: {model})")
                    continue
                    
            except Exception as model_error:
                logger.warning(f"モデル {model} でエラー: {model_error}")
                continue
        
        # 全てのモデルで失敗した場合
        logger.warning("全てのClaudeモデルで失敗。フォールバック処理を使用")
        return extract_keywords_fallback(message)
            
    except Exception as e:
        logger.error(f"キーワード抽出エラー: {e}")
        return extract_keywords_fallback(message)

def extract_keywords_fallback(message):
    """フォールバック用キーワード抽出"""
    # 基本的な日本語キーワード抽出
    import re
    
    # カタカナ、ひらがな、漢字、英数字の組み合わせ
    keywords = re.findall(r'[ァ-ヶー]+|[ぁ-ん]+|[一-龯]+|[A-Za-z0-9]+', message)
    
    # 長さでフィルタリング（2文字以上）
    keywords = [k for k in keywords if len(k) >= 2]
    
    # ストップワード除去
    stop_words = ['です', 'ます', 'した', 'ある', 'いる', 'する', 'なる', 'れる', 'られる', 'せる', 'させる']
    keywords = [k for k in keywords if k not in stop_words]
    
    return keywords[:5]

def parse_reminder_request(message):
    """
    リマインダーリクエストを解析
    例: "毎日10時に薬を飲む" → {time: "10:00", repeat: "daily", message: "薬を飲む"}
    """
    patterns = [
        # 毎日パターン
        (r'毎日(\d{1,2})時(\d{0,2})分?に?(.+)', 'daily'),
        (r'毎日(\d{1,2}):(\d{2})に?(.+)', 'daily'),
        # 平日パターン
        (r'平日(\d{1,2})時(\d{0,2})分?に?(.+)', 'weekdays'),
        (r'平日(\d{1,2}):(\d{2})に?(.+)', 'weekdays'),
        # 週末パターン
        (r'週末(\d{1,2})時(\d{0,2})分?に?(.+)', 'weekends'),
        (r'週末(\d{1,2}):(\d{2})に?(.+)', 'weekends'),
        # 特定曜日パターン
        (r'毎週([月火水木金土日])曜日?(\d{1,2})時(\d{0,2})分?に?(.+)', 'weekly'),
        (r'毎週([月火水木金土日])曜日?(\d{1,2}):(\d{2})に?(.+)', 'weekly'),
        # 一回限りパターン
        (r'(\d{1,2})時(\d{0,2})分?に?(.+)', 'once'),
        (r'(\d{1,2}):(\d{2})に?(.+)', 'once'),
    ]
    
    for pattern, repeat_type in patterns:
        match = re.match(pattern, message)
        if match:
            groups = match.groups()
            
            if repeat_type == 'weekly':
                day_map = {'月': 'mon', '火': 'tue', '水': 'wed', '木': 'thu', '金': 'fri', '土': 'sat', '日': 'sun'}
                day = day_map.get(groups[0], 'mon')
                hour = int(groups[1])
                minute = int(groups[2]) if groups[2] else 0
                reminder_message = groups[3]
                return {
                    'time': f"{hour:02d}:{minute:02d}",
                    'repeat': repeat_type,
                    'days': [day],
                    'message': reminder_message.strip()
                }
            else:
                hour = int(groups[0])
                minute = int(groups[1]) if groups[1] else 0
                reminder_message = groups[2] if len(groups) > 2 else groups[1]
                
                days = []
                if repeat_type == 'weekdays':
                    days = ['mon', 'tue', 'wed', 'thu', 'fri']
                elif repeat_type == 'weekends':
                    days = ['sat', 'sun']
                elif repeat_type == 'daily':
                    days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
                
                return {
                    'time': f"{hour:02d}:{minute:02d}",
                    'repeat': repeat_type,
                    'days': days,
                    'message': reminder_message.strip()
                }
    
    # リマインダー削除パターン
    if re.match(r'リマインダー.*削除|削除.*リマインダー', message):
        return {'action': 'delete'}
    
    # リマインダー一覧パターン
    if re.match(r'リマインダー.*一覧|一覧.*リマインダー', message):
        return {'action': 'list'}
    
    return None

def save_reminder(user_id, reminder_data):
    """リマインダーをSupabaseに保存"""
    try:
        if not supabase_client:
            return False
            
        result = supabase_client.table('reminders').insert({
            'user_id': user_id,
            'message': reminder_data['message'],
            'reminder_time': reminder_data['time'],
            'repeat_pattern': reminder_data['repeat'],
            'repeat_days': reminder_data.get('days', [])
        }).execute()
        
        if result.data:
            return result.data[0]['id']
        return False
        
    except Exception as e:
        logger.error(f"リマインダー保存エラー: {e}")
        return False

def get_user_reminders(user_id):
    """ユーザーのリマインダー一覧をSupabaseから取得"""
    try:
        if not supabase_client:
            return []
            
        result = supabase_client.table('reminders').select(
            'id, message, reminder_time, repeat_pattern, repeat_days, is_active'
        ).eq('user_id', user_id).eq('is_active', True).order('reminder_time').execute()
        
        return result.data if result.data else []
        
    except Exception as e:
        logger.error(f"リマインダー取得エラー: {e}")
        return []

def delete_user_reminders(user_id):
    """ユーザーのリマインダーを削除（非アクティブ化）"""
    try:
        if not supabase_client:
            return False
            
        result = supabase_client.table('reminders').update({
            'is_active': False,
            'updated_at': 'now()'
        }).eq('user_id', user_id).eq('is_active', True).execute()
        
        return len(result.data) > 0 if result.data else False
        
    except Exception as e:
        logger.error(f"リマインダー削除エラー: {e}")
        return False

def send_reminder_notification(user_id, message):
    """リマインダー通知を送信"""
    try:
        if user_id.startswith('line_') and line_bot_api:
            # LINE通知
            line_user_id = user_id.replace('line_', '')
            line_bot_api.push_message(
                line_user_id,
                TextSendMessage(text=f"🔔 リマインダー\n\n{message}")
            )
            logger.info(f"リマインダー送信成功: {user_id} - {message[:50]}...")
            return True
        elif user_id.startswith('chatwork_'):
            # Chatwork通知（実装可能）
            logger.info(f"Chatworkリマインダー: {user_id} - {message}")
            return True
        else:
            logger.warning(f"未対応のプラットフォーム: {user_id}")
            return False
            
    except Exception as e:
        logger.error(f"リマインダー通知エラー: {e}")
        return False

def check_and_send_reminders():
    """定期的にリマインダーをチェックして送信"""
    try:
        if not supabase_client:
            return
            
        # 現在時刻
        now = datetime.now(pytz.timezone('Asia/Tokyo'))
        current_time = now.strftime('%H:%M')
        current_date = now.date().isoformat()
        current_day = now.strftime('%a').lower()
        
        # アクティブなリマインダーを取得
        result = supabase_client.table('reminders').select('*').eq('is_active', True).like('reminder_time', f'{current_time}%').execute()
        
        if not result.data:
            return
            
        for reminder in result.data:
            # 今日送信済みかチェック
            if reminder.get('last_sent_date') and reminder['last_sent_date'] >= current_date:
                continue
                
            should_send = False
            
            if reminder['repeat_pattern'] == 'once':
                should_send = True
            elif reminder['repeat_pattern'] == 'daily':
                should_send = True
            elif reminder['repeat_pattern'] == 'weekdays' and current_day in ['mon', 'tue', 'wed', 'thu', 'fri']:
                should_send = True
            elif reminder['repeat_pattern'] == 'weekends' and current_day in ['sat', 'sun']:
                should_send = True
            elif reminder['repeat_pattern'] == 'weekly' and current_day in reminder.get('repeat_days', []):
                should_send = True
            
            if should_send:
                # 通知送信
                success = send_reminder_notification(reminder['user_id'], reminder['message'])
                
                if success:
                    # 送信日を更新
                    update_data = {'last_sent_date': current_date}
                    
                    # 一回限りのリマインダーは非アクティブ化
                    if reminder['repeat_pattern'] == 'once':
                        update_data['is_active'] = False
                    
                    supabase_client.table('reminders').update(update_data).eq('id', reminder['id']).execute()
        
    except Exception as e:
        logger.error(f"リマインダーチェックエラー: {e}")

def get_recent_line_conversations(user_id, limit=10):
    """指定したLINEユーザーの最近の会話履歴をSupabaseから取得"""
    try:
        if not supabase_client:
            logger.error("Supabaseクライアント未接続")
            return []
        
        # 最近の会話を時系列順で取得
        result = supabase_client.table('conversations').select(
            'user_message, ai_response, created_at'
        ).eq('user_id', user_id).order('created_at', desc=True).limit(limit).execute()
        
        conversations = result.data if result.data else []
        
        # 時系列順（古い順）に並び替えて返す
        conversations.reverse()
        
        logger.info(f"LINE会話履歴取得: {len(conversations)}件 (user_id: {user_id})")
        return conversations
        
    except Exception as e:
        logger.error(f"LINE会話履歴取得エラー: {e}")
        return []

def search_database_for_context(keywords, user_id, limit=5):
    """データベース検索のメインエントリーポイント"""
    try:
        # 直接基本検索を使用（perfect検索関数が未定義のため）
        results = search_database_basic_fallback(keywords, user_id, limit)
        
        if results:
            logger.info(f"検索成功: {len(results)} 件")
            return results
        else:
            logger.warning("検索結果なし")
            return []
            
    except Exception as e:
        logger.error(f"検索システムエラー: {e}")
        return []

def search_database_basic_fallback(keywords, user_id, limit=5):
    """基本検索（Supabase版）"""
    try:
        if not supabase_client:
            logger.error("Supabaseクライアント未接続")
            return []
        
        # キーワード処理
        if isinstance(keywords, list):
            search_terms = [str(k) for k in keywords if k]
        elif isinstance(keywords, dict):
            search_terms = [str(k) for k in keywords.get('primary_keywords', []) if k]
        else:
            search_terms = [str(keywords)] if keywords else []
        
        if not search_terms:
            # キーワードがない場合は最新のconversationsデータを返す
            result = supabase_client.table('conversations').select(
                'user_message, ai_response, created_at'
            ).is_('message', 'not.null').order('created_at', desc=True).limit(limit).execute()
            
            results = []
            if result.data:
                for row in result.data:
                    results.append({
                        'user_message': row['user_message'],
                        'ai_response': row['ai_response'],
                        'created_at': row['created_at'],
                        'source': 'conversations'
                    })
            
            logger.info(f"基本検索（最新データ）: {len(results)} 件")
            return results
        
        # キーワード検索（conversationsテーブル）
        results = []
        for term in search_terms[:3]:  # 最大3個のキーワード
            if len(term.strip()) >= 2:
                # user_messageで検索
                result1 = supabase_client.table('conversations').select(
                    'user_message, ai_response, created_at'
                ).ilike('user_message', f'%{term}%').order('created_at', desc=True).limit(limit).execute()
                
                if result1.data:
                    for row in result1.data:
                        results.append({
                            'user_message': row['user_message'],
                            'ai_response': row['ai_response'],
                            'created_at': row['created_at'],
                            'source': 'conversations'
                        })
                
                # ai_responseでも検索
                result2 = supabase_client.table('conversations').select(
                    'user_message, ai_response, created_at'
                ).ilike('ai_response', f'%{term}%').order('created_at', desc=True).limit(limit).execute()
                
                if result2.data:
                    for row in result2.data:
                        results.append({
                            'user_message': row['user_message'],
                            'ai_response': row['ai_response'],
                            'created_at': row['created_at'],
                            'source': 'conversations'
                        })
        
        # 重複除去
        unique_results = []
        seen_messages = set()
        
        for result in results:
            message = result.get('user_message', '') or ''
            message_key = message[:50]  # 最初の50文字
            
            if message_key and message_key not in seen_messages:
                seen_messages.add(message_key)
                unique_results.append(result)
        
        final_results = unique_results[:limit]
        logger.info(f"基本検索成功: {len(final_results)} 件")
        return final_results
        
    except Exception as e:
        logger.error(f"基本検索エラー: {e}")
        return []

def generate_ai_response_with_context(user_message, context_data, user_id):
    """文脈情報を使ってAI回答を生成（Dify優先、Claude APIフォールバック）"""
    try:
        # Dify APIを優先的に使用
        if DIFY_API_KEY and USE_DIFY_API:
            dify_response = call_dify_api(user_message, context_data, user_id)
            if dify_response and len(str(dify_response).strip()) > 0:
                logger.info("Dify APIで回答生成成功")
                return dify_response
            logger.warning("Dify API回答生成に失敗、Claude APIにフォールバック")
        
        # Claude APIフォールバック
        if not ANTHROPIC_API_KEY:
            return generate_fallback_response(user_message, context_data)
            
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01'
        }
        
        # 文脈情報をフォーマット
        context_text = ""
        if context_data:
            context_text = "\n\n【過去の会話から見つかった関連情報】\n"
            for i, item in enumerate(context_data, 1):
                created_at = item.get('created_at', 'Unknown')
                if hasattr(created_at, 'strftime'):
                    date_str = created_at.strftime('%Y-%m-%d %H:%M')
                else:
                    date_str = str(created_at)[:16]  # 文字列の場合は最初の16文字
                
                user_msg = item.get('user_message', '') or ''
                ai_resp = item.get('ai_response', '') or ''
                
                context_text += f"【情報{i}】({date_str})\n"
                context_text += f"質問: {user_msg[:150]}...\n"
                context_text += f"内容: {ai_resp[:300]}...\n\n"
        
        prompt = f"""
あなたは優秀なAIアシスタントです。ユーザーの質問に対して、過去の会話履歴から見つかった具体的な情報を最大限活用して回答してください。

ユーザーの質問: {user_message}

{context_text}

重要な指針:
1. **具体的な情報を優先**: URL、ファイル名、日付、場所などの具体的な情報があれば必ず含める
2. **過去の情報を活用**: 見つかった過去の会話から関連する具体的な内容を抽出して回答に含める
3. **直接的な回答**: 一般論ではなく、実際に見つかった情報を使って具体的に答える
4. **URL抽出**: 過去のデータにURLやリンクがあれば必ず表示する
5. **ファイル情報**: ファイル名、保存場所、作成日などがあれば明記する
6. **見つからない場合のみ**: 本当に関連情報が見つからない場合のみ一般的な回答をする

過去のデータに具体的な情報（URL、ファイル、場所など）がある場合は、それを最優先で回答に含めてください。

回答:"""

        # 実際に利用可能なClaudeモデルを試行
        models_to_try = [
            {
                "model": "claude-3-5-sonnet-20241022", # Claude 3.5 Sonnet (最新安定版)
                "max_tokens": 8000,
                "temperature": 0.3
            },
            {
                "model": "claude-3-5-haiku-20241022",  # Claude 3.5 Haiku (高速)
                "max_tokens": 4000,
                "temperature": 0.2
            },
            {
                "model": "claude-3-opus-20240229",     # Claude 3 Opus (高性能)
                "max_tokens": 4000,
                "temperature": 0.3
            }
        ]
        
        for model_config in models_to_try:
            try:
                data = {
                    "model": model_config["model"],
                    "max_tokens": model_config["max_tokens"],
                    "temperature": model_config["temperature"],
                    "messages": [
                        {
                            "role": "user", 
                            "content": prompt
                        }
                    ]
                }
                
                response = requests.post(
                    'https://api.anthropic.com/v1/messages',
                    headers=headers,
                    json=data,
                    timeout=60  # Claude 4は処理時間が長い可能性
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"AI回答生成成功 (モデル: {model_config['model']})")
                    return result['content'][0]['text']
                elif response.status_code == 404:
                    # モデルが見つからない場合、次のモデルを試行
                    logger.warning(f"モデル {model_config['model']} が利用できません。次のモデルを試行中...")
                    continue
                else:
                    logger.warning(f"Claude API エラー: {response.status_code} (モデル: {model_config['model']})")
                    continue
                    
            except Exception as model_error:
                logger.warning(f"モデル {model_config['model']} でエラー: {model_error}")
                continue
        
        # 全てのモデルで失敗した場合
        logger.error("全てのClaudeモデルで失敗。フォールバック回答を生成")
        return generate_fallback_response(user_message, context_data)
            
    except Exception as e:
        logger.error(f"AI回答生成エラー: {e}")
        return generate_fallback_response(user_message, context_data)

def generate_fallback_response(user_message, context_data):
    """APIが利用できない場合のフォールバック回答"""
    if context_data:
        response = f"お探しの情報について、過去の会話から関連する内容を見つけました：\n\n"
        for i, item in enumerate(context_data[:2], 1):
            response += f"**{i}. {item['created_at'].strftime('%Y年%m月%d日')}の会話**\n"
            response += f"質問: {item['user_message'][:100]}...\n"
            response += f"回答: {item['ai_response'][:200]}...\n\n"
        response += "詳細な情報については、ANTHROPIC_API_KEYを設定してClaude APIを有効にしてください。"
    else:
        response = f"""
申し訳ございませんが、現在AIサービスが利用できません。

**お問い合わせ内容**: {user_message}

基本的な対応方法：
1. ANTHROPIC_API_KEYが正しく設定されているか確認してください
2. しばらく時間をおいてから再度お試しください
3. 詳細なサポートが必要な場合は管理者にお問い合わせください

過去の会話履歴からの関連情報は見つかりませんでした。
"""
    return response

def save_conversation_to_db(user_id, conversation_id, user_message, ai_response, keywords, context_used, response_time_ms, source_platform='web'):
    """会話をSupabaseに保存"""
    try:
        if not supabase_client:
            return False
        
        # context_usedのdatetime型をstring型に変換
        context_used_json = None
        if context_used:
            # datetime型を文字列に変換
            for item in context_used:
                if isinstance(item.get('created_at'), datetime):
                    item['created_at'] = item['created_at'].isoformat()
            context_used_json = json.dumps(context_used, ensure_ascii=False)
        
        data = {
            'user_id': user_id,
            'conversation_id': conversation_id,
            'user_message': user_message,
            'ai_response': ai_response,
            'keywords': keywords,
            'context_used': context_used_json,
            'response_time_ms': response_time_ms,
            'source_platform': source_platform,
            'created_at': datetime.now().isoformat()
        }
        
        result = supabase_client.table('conversations').insert(data).execute()
        return bool(result.data)
        
    except Exception as e:
        logger.error(f"会話保存エラー: {e}")
        return False

# レート制限用の辞書（簡易実装）
user_requests = {}

# その他の設定
SKLEARN_N_JOBS = int(os.getenv('SKLEARN_N_JOBS', '1'))  # scikit-learn並列処理数
NUMPY_MEMORY_LIMIT = int(os.getenv('NUMPY_MEMORY_LIMIT', '256'))  # NumPyメモリ制限(MB)

def rate_limit(max_requests=10, window_seconds=60):
    """レート制限デコレータ"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 簡易的なレート制限実装
            # 本番環境ではRedisを使用することを推奨
            return func(*args, **kwargs)
        return wrapper
    return decorator

# =================================================================
# 5. Webアプリケーションルート
# =================================================================
@app.route('/')
def index():
    """メインページ"""
    return send_from_directory('.', 'index.html')

@app.route('/dashboard')
def dashboard():
    """ダッシュボードページ"""
    return send_from_directory('.', 'dashboard.html')

@app.route('/health')
def health():
    """ヘルスチェック"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': 'connected' if supabase_client else 'disconnected'
    })

# =================================================================
# 6. チャットAPI（メイン機能）
# =================================================================
@app.route('/api/chat', methods=['POST'])
@rate_limit(max_requests=10, window_seconds=60)
def chat():
    """ストリーミング対応チャットAPI"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '無効なリクエストです'}), 400

        user_id = data.get('user_id')
        user_message = data.get('message', '').strip()
        conversation_id = data.get('conversation_id')

        if not user_id or not user_message:
            return jsonify({'error': 'user_idとmessageは必須です'}), 400

        def generate_response():
            start_time = time.time()
            
            try:
                # ステップ1: キーワード抽出
                yield f"data: {json.dumps({'text': ''})}\n\n"  # 初期化
                
                keywords = extract_keywords_with_ai(user_message)
                logger.info(f"キーワード抽出完了: {len(keywords) if keywords else 0}個")

                # ステップ2: データベース検索
                context_data = search_database_for_context(keywords, user_id)
                logger.info(f"検索された文脈データ: {len(context_data)}件")

                # ステップ3: AI回答生成（ストリーミング対応）
                full_response = generate_ai_response_with_context(user_message, context_data, user_id)
                
                # 文字ごとにストリーミング送信
                # パフォーマンス最適化：チャンクサイズを大きくして遅延を減らす
                chunk_size = 10  # 10文字ずつ送信
                for i in range(0, len(full_response), chunk_size):
                    chunk = full_response[i:i+chunk_size]
                    yield f"data: {json.dumps({'text': chunk})}\n\n"
                    time.sleep(0.05)  # チャンクごとの遅延

                # ステップ4: データベースに保存
                response_time_ms = int((time.time() - start_time) * 1000)
                save_conversation_to_db(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    user_message=user_message,
                    ai_response=full_response,
                    keywords=keywords,
                    context_used=context_data,
                    response_time_ms=response_time_ms,
                    source_platform='web'
                )

                # ストリーム終了通知
                yield f"data: {json.dumps({'text': '', 'done': True})}\n\n"

            except Exception as e:
                logger.error(f"チャット処理エラー: {e}")
                error_message = f"エラーが発生しました: {str(e)}"
                yield f"data: {json.dumps({'text': error_message, 'error': True})}\n\n"

        return Response(generate_response(), mimetype='text/event-stream')

    except Exception as e:
        logger.error(f"チャットAPIエラー: {e}")
        return jsonify({'error': str(e)}), 500

# =================================================================
# 7. 統計API
# =================================================================
@app.route('/api/stats')
def get_stats():
    """統計情報をSupabaseから取得"""
    try:
        if not supabase_client:
            return jsonify({'error': 'Supabase接続エラー'}), 500

        # 基本統計（30日間）
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
        result = supabase_client.table('conversations').select(
            'user_id, response_time_ms, satisfaction_rating'
        ).gte('created_at', thirty_days_ago).execute()
        
        conversations = result.data if result.data else []
        total_conversations = len(conversations)
        unique_users = len(set(conv['user_id'] for conv in conversations))
        
        response_times = [conv['response_time_ms'] for conv in conversations if conv.get('response_time_ms')]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        ratings = [conv['satisfaction_rating'] for conv in conversations if conv.get('satisfaction_rating')]
        satisfaction_rate = (sum(ratings) / len(ratings) * 20) if ratings else 0
        
        basic_stats = {
            'total_conversations': total_conversations,
            'unique_users': unique_users,
            'avg_response_time': avg_response_time,
            'satisfaction_rate': satisfaction_rate
        }
        
        # 日別統計（7日間）
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        result = supabase_client.table('conversations').select(
            'created_at'
        ).gte('created_at', seven_days_ago).execute()
        
        daily_counts = {}
        if result.data:
            for conv in result.data:
                date = conv['created_at'][:10]  # YYYY-MM-DD形式
                daily_counts[date] = daily_counts.get(date, 0) + 1
        
        daily_stats = [{'date': date, 'conversations': count} for date, count in daily_counts.items()]
        daily_stats.sort(key=lambda x: x['date'], reverse=True)
        
        # 時間別統計は簡略化（全体集計）
        hourly_stats = []
        
        return jsonify({
            'basic_stats': basic_stats,
            'daily_stats': daily_stats,
            'hourly_stats': hourly_stats
        })
        
    except Exception as e:
        logger.error(f"統計取得エラー: {e}")
        return jsonify({'error': str(e)}), 500

# =================================================================
# 8. LINE Webhook
# =================================================================
@app.route('/webhook/line', methods=['POST'])
@app.route('/api/line/webhook', methods=['POST'])  # 追加パス
def line_webhook():
    """LINE Webhook"""
    if not line_handler:
        return 'LINE not configured', 400

    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    try:
        line_handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("LINE Webhook signature verification failed")
        return 'Invalid signature', 400
    except Exception as e:
        logger.error(f"LINE Webhook error: {e}")
        return 'Error', 500

    return 'OK'

@line_handler.add(MessageEvent, message=TextMessage)
def handle_line_message(event):
    """LINEメッセージハンドラ"""
    try:
        user_id = f"line_{event.source.user_id}"
        user_message = event.message.text
        
        logger.info(f"LINE受信: {user_id} - メッセージ長: {len(user_message)}文字")
        
        # 過去10件の会話履歴を取得
        recent_conversations = get_recent_line_conversations(user_id, limit=10)
        logger.info(f"過去の会話履歴: {len(recent_conversations)}件取得")
        
        # 会話履歴を文字列形式に整形
        conversation_history = ""
        if recent_conversations:
            conversation_history = "\n\n=== 過去の会話履歴 ===\n"
            for conv in recent_conversations:
                created_at = conv['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                conversation_history += f"\n[{created_at}]\n"
                conversation_history += f"ユーザー: {conv['user_message']}\n"
                conversation_history += f"AI: {conv['ai_response'][:100]}...\n"  # 長い場合は省略
            conversation_history += "\n=== 履歴終了 ===\n\n"
        
        # キーワード抽出
        keywords = extract_keywords_with_ai(user_message)
        logger.info(f"キーワード抽出: {len(keywords) if keywords else 0}個")
        
        # データベース検索（関連する過去の会話）
        context_data = search_database_for_context(keywords, user_id)
        
        # 会話履歴を含めたコンテキストデータの作成
        enhanced_context_data = context_data
        if conversation_history:
            # 会話履歴を最初に追加
            history_context = {
                'user_message': '過去の会話履歴',
                'ai_response': conversation_history,
                'created_at': datetime.now(),
                'final_score': 100  # 高いスコアを付けて優先度を上げる
            }
            enhanced_context_data = [history_context] + context_data
        
        # リマインダー処理をチェック
        reminder_data = parse_reminder_request(user_message)
        if reminder_data:
            if reminder_data.get('action') == 'list':
                # リマインダー一覧
                reminders = get_user_reminders(user_id)
                if reminders:
                    ai_response = "📋 現在設定されているリマインダー:\n\n"
                    for i, reminder in enumerate(reminders, 1):
                        time_str = str(reminder['reminder_time'])[:5]
                        repeat_str = {
                            'once': '一回のみ',
                            'daily': '毎日',
                            'weekdays': '平日',
                            'weekends': '週末',
                            'weekly': '毎週'
                        }.get(reminder['repeat_pattern'], reminder['repeat_pattern'])
                        
                        if reminder['repeat_pattern'] == 'weekly' and reminder['repeat_days']:
                            day_map = {'mon': '月', 'tue': '火', 'wed': '水', 'thu': '木', 'fri': '金', 'sat': '土', 'sun': '日'}
                            days_str = ''.join([day_map.get(d, d) for d in reminder['repeat_days']])
                            repeat_str += f" {days_str}曜日"
                        
                        ai_response += f"{i}. {time_str} {repeat_str}: {reminder['message']}\n"
                else:
                    ai_response = "現在、設定されているリマインダーはありません。\n\n例えば以下のように設定できます：\n・毎日10時に薬を飲む\n・平日8時に出勤準備\n・毎週月曜日9時に会議"
            elif reminder_data.get('action') == 'delete':
                # リマインダー削除
                if delete_user_reminders(user_id):
                    ai_response = "✅ リマインダーをすべて削除しました。"
                else:
                    ai_response = "リマインダーの削除に失敗しました。"
            else:
                # リマインダー設定
                reminder_id = save_reminder(user_id, reminder_data)
                if reminder_id:
                    time_str = reminder_data['time']
                    repeat_str = {
                        'once': '一回のみ',
                        'daily': '毎日',
                        'weekdays': '平日',
                        'weekends': '週末',
                        'weekly': '毎週'
                    }.get(reminder_data['repeat'], reminder_data['repeat'])
                    
                    if reminder_data['repeat'] == 'weekly' and reminder_data.get('days'):
                        day_map = {'mon': '月', 'tue': '火', 'wed': '水', 'thu': '木', 'fri': '金', 'sat': '土', 'sun': '日'}
                        days_str = ''.join([day_map.get(d, d) for d in reminder_data['days']])
                        repeat_str += f" {days_str}曜日"
                    
                    ai_response = f"✅ リマインダーを設定しました！\n\n⏰ 時刻: {time_str}\n🔄 繰り返し: {repeat_str}\n📝 内容: {reminder_data['message']}\n\n設定したリマインダーは指定時刻に通知されます。"
                else:
                    ai_response = "リマインダーの設定に失敗しました。もう一度お試しください。"
        else:
            # 通常のAI回答生成（会話履歴を含むコンテキストで）
            ai_response = generate_ai_response_with_context(user_message, enhanced_context_data, user_id)
        
        # データベースに保存
        save_conversation_to_db(
            user_id=user_id,
            conversation_id=None,
            user_message=user_message,
            ai_response=ai_response,
            keywords=keywords,
            context_used=context_data,  # 元のcontext_dataを保存
            response_time_ms=0,
            source_platform='line'
        )
        
        # LINE返信
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=ai_response)
        )
        
    except Exception as e:
        logger.error(f"LINE メッセージ処理エラー: {e}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="申し訳ございません。エラーが発生しました。")
        )

# =================================================================
# 9. Chatwork Webhook
# =================================================================
@app.route('/webhook/chatwork', methods=['POST'])
def chatwork_webhook():
    """Chatwork Webhook"""
    try:
        if not CHATWORK_WEBHOOK_TOKEN:
            return 'Chatwork not configured', 400
            
        # Webhook認証
        webhook_token = request.headers.get('X-ChatWorkWebhookToken')
        if webhook_token != CHATWORK_WEBHOOK_TOKEN:
            return 'Unauthorized', 401
            
        data = request.get_json()
        if not data:
            return 'No data', 400
            
        # メッセージ処理
        webhook_event = data.get('webhook_event')
        if webhook_event and webhook_event.get('type') == 'mention_to_me':
            body = webhook_event.get('body', '')
            account_id = webhook_event.get('from_account_id')
            room_id = webhook_event.get('room_id')
            
            user_id = f"chatwork_{account_id}"
            
            # AIが言及されている場合のみ処理
            if '[To:AI]' in body or 'AI' in body:
                # キーワード抽出
                keywords = extract_keywords_with_ai(body)
                
                # データベース検索
                context_data = search_database_for_context(keywords, user_id, limit=10)  # より多くの結果を取得
                
                # AI回答生成
                ai_response = generate_ai_response_with_context(body, context_data, user_id)
                
                # データベースに保存
                save_conversation_to_db(
                    user_id=user_id,
                    conversation_id=str(room_id),
                    user_message=body,
                    ai_response=ai_response,
                    keywords=keywords,
                    context_used=context_data,
                    response_time_ms=0,
                    source_platform='chatwork'
                )
                
                # Chatworkに返信
                chatwork_url = f"https://api.chatwork.com/v2/rooms/{room_id}/messages"
                chatwork_headers = {
                    'X-ChatWorkToken': CHATWORK_API_TOKEN,
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
                chatwork_data = {'body': ai_response}
                
                requests.post(chatwork_url, headers=chatwork_headers, data=chatwork_data)
        
        return 'OK'
        
    except Exception as e:
        logger.error(f"Chatwork Webhook エラー: {e}")
        return 'Error', 500

# =================================================================
# 11. デバッグ・管理用API
# =================================================================
@app.route('/api/debug/conversations')
def debug_conversations():
    """デバッグ用：Supabase内の会話を確認"""
    try:
        if not supabase_client:
            return jsonify({'error': 'Supabase接続エラー'}), 500
        
        # conversationsテーブルから取得
        result = supabase_client.table('conversations').select(
            'id, user_id, user_message, ai_response, keywords, created_at'
        ).order('created_at', desc=True).limit(10).execute()
        
        conversations = []
        if result.data:
            for row in result.data:
                conversations.append({
                    **row,
                    'source': 'conversations'
                })
        
        # conversationsテーブルの総件数
        count_result = supabase_client.table('conversations').select('*', count='exact').execute()
        conv_total = count_result.count if count_result.count is not None else 0
        
        return jsonify({
            'conversations_table': {
                'total': conv_total,
                'recent': conversations
            },
            'external_chat_logs_table': {
                'total': 0,
                'recent': []
            }
        })
        
    except Exception as e:
        logger.error(f"デバッグ取得エラー: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/search/<query>')
def debug_search(query):
    """検索システムのデバッグ"""
    try:
        user_id = "debug_user"
        
        # キーワード抽出
        keywords = extract_keywords_with_ai(query)
        
        # 通常検索実行
        results = search_database_for_context(keywords, user_id, limit=10)
        
        # 各結果の情報
        detailed_results = []
        for i, result in enumerate(results):
            detailed_result = {
                'rank': i + 1,
                'user_message': result.get('user_message', '')[:100],
                'ai_response': result.get('ai_response', '')[:200],
                'created_at': str(result.get('created_at', '')),
                'source': result.get('source', '')
            }
            detailed_results.append(detailed_result)
        
        return jsonify({
            'query': query,
            'keywords': keywords,
            'total_results': len(results),
            'results': detailed_results
        })
        
    except Exception as e:
        logger.error(f"検索デバッグエラー: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/user-stats/<user_id>')
def debug_user_stats(user_id):
    """ユーザーの統計情報（Supabase版）"""
    try:
        if not supabase_client:
            return jsonify({'error': 'Supabase接続エラー'}), 500
        
        # ユーザーの会話統計
        result = supabase_client.table('conversations').select(
            'created_at, keywords'
        ).eq('user_id', user_id).execute()
        
        conversations = result.data if result.data else []
        total_conversations = len(conversations)
        
        if conversations:
            dates = set(conv['created_at'][:10] for conv in conversations)
            active_days = len(dates)
            first_conversation = min(conv['created_at'] for conv in conversations)
            last_conversation = max(conv['created_at'] for conv in conversations)
        else:
            active_days = 0
            first_conversation = None
            last_conversation = None
        
        stats = {
            'total_conversations': total_conversations,
            'active_days': active_days,
            'first_conversation': first_conversation,
            'last_conversation': last_conversation
        }
        
        # キーワード統計（簡略化）
        keyword_counts = {}
        for conv in conversations:
            if conv.get('keywords'):
                for keyword in conv['keywords']:
                    keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        
        frequent_keywords = [
            {'keyword': k, 'count': v} 
            for k, v in sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        return jsonify({
            'user_id': user_id,
            'stats': stats,
            'frequent_keywords': frequent_keywords
        })
        
    except Exception as e:
        logger.error(f"ユーザー統計デバッグエラー: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/feedback', methods=['POST'])
def record_feedback():
    """会話フィードバックをSupabaseに記録"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '無効なリクエスト'}), 400
            
        conversation_id = data.get('conversation_id')
        rating = data.get('rating')
        
        if not conversation_id or rating is None:
            return jsonify({'error': 'conversation_idとratingは必須です'}), 400
            
        if not (1 <= rating <= 5):
            return jsonify({'error': 'ratingは1から5の間である必要があります'}), 400
            
        if not supabase_client:
            return jsonify({'error': 'Supabase接続エラー'}), 500
        
        # 満足度を更新
        result = supabase_client.table('conversations').update({
            'satisfaction_rating': rating,
            'updated_at': datetime.now().isoformat()
        }).eq('id', conversation_id).execute()
        
        if result.data:
            return jsonify({'success': True, 'message': 'フィードバックを記録しました'})
        else:
            return jsonify({'error': '該当する会話が見つかりません'}), 404
        
    except Exception as e:
        logger.error(f"フィードバック記録エラー: {e}")
        return jsonify({'error': str(e)}), 500
def create_app():
    """アプリケーションファクトリ"""
    # データベース初期化
    init_database()
    logger.info("アプリケーション初期化完了")
    return app

# スケジューラーのジョブを設定
def setup_scheduler():
    """スケジューラーのジョブを設定"""
    # 既存のジョブをクリア
    scheduler.remove_all_jobs()
    
    # 毎分実行（リマインダーチェック）
    scheduler.add_job(
        func=check_and_send_reminders,
        trigger='cron',
        minute='*',  # 毎分
        id='reminder_checker',
        replace_existing=True
    )
    
    logger.info("スケジューラージョブを設定しました")

# アプリケーション初期化（本番環境用）
with app.app_context():
    init_database()
    setup_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("スケジューラーを開始しました")

if __name__ == '__main__':
    # 環境に応じた設定
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    host = os.getenv('HOST', '0.0.0.0')
    
    # Pythonバージョン確認
    python_version = os.getenv('PYTHON_VERSION', '3.11.7')
    logger.info(f"Pythonバージョン要件: {python_version}")
    
    # 環境設定のサマリーをログ出力
    logger.info(f"アプリケーション起動設定:")
    logger.info(f"  - Flask環境: {os.getenv('FLASK_ENV', 'development')}")
    logger.info(f"  - ポート: {port}")
    logger.info(f"  - デバッグモード: {debug}")
    logger.info(f"  - ホスト: {host}")
    logger.info(f"  - CORS許可オリジン: {allowed_origins}")
    logger.info(f"  - Dify API: {'Configured and Active' if (DIFY_API_KEY and USE_DIFY_API) else 'Not configured or inactive'}")
    logger.info(f"  - Claude API: {'Configured' if ANTHROPIC_API_KEY else 'Not configured'}")
    logger.info(f"  - LINE Bot: {'Configured' if LINE_CHANNEL_ACCESS_TOKEN else 'Not configured'}")
    logger.info(f"  - Supabase: {'Configured' if SUPABASE_URL else 'Not configured'}")
    
    logger.info(f"アプリケーションを起動中... Port: {port}, Debug: {debug}")
    
    # 開発環境でのスケジューラー確認（初期化は既に完了済み）
    if debug and not scheduler.running:
        scheduler.start()
        logger.info("スケジューラーを開始しました（開発環境）")
    
    try:
        app.run(host=host, port=port, debug=debug)
    finally:
        # アプリケーション終了時にスケジューラーを停止
        if scheduler.running:
            scheduler.shutdown()
            logger.info("スケジューラーを停止しました")

# Gunicorn用のアプリケーションオブジェクト
application = app