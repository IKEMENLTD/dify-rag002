from flask import Blueprint, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from config import Config
import logging

# Initialize LINE Bot
line_bot_bp = Blueprint('line_bot', __name__)
line_bot_api = LineBotApi(Config.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(Config.LINE_CHANNEL_SECRET)

logger = logging.getLogger(__name__)

@line_bot_bp.route('/webhook/line', methods=['POST'])
def line_webhook():
    """Handle LINE webhook"""
    # Get X-Line-Signature header value
    signature = request.headers.get('X-Line-Signature', '')
    
    # Get request body as text
    body = request.get_data(as_text=True)
    logger.info("LINE webhook request body: " + body)
    
    # Handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature. Check your channel secret.")
        abort(400)
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """Handle LINE text messages"""
    try:
        # Get user message
        user_message = event.message.text
        
        # Import chat functions from main app
        from app import call_dify_api, call_claude_api
        
        # Try Dify first
        response = call_dify_api(user_message)
        
        if not response:
            # Fallback to Claude
            response = call_claude_api(user_message)
        
        if not response:
            response = "申し訳ございません。現在AIサービスが利用できません。"
        
        # Reply to user
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=response)
        )
    
    except Exception as e:
        logger.error(f"Error handling LINE message: {str(e)}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="エラーが発生しました。しばらくしてから再度お試しください。")
        )