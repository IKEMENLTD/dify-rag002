from flask import Blueprint, request, abort, jsonify
import os
import json
import requests
import logging
import hmac
import hashlib
import base64

# Initialize LINE Bot
line_bot_bp = Blueprint('line_bot', __name__)
logger = logging.getLogger(__name__)

LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', '')
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '')

@line_bot_bp.route('/webhook/line', methods=['POST'])
def line_webhook():
    """Handle LINE webhook"""
    # Get X-Line-Signature header value
    signature = request.headers.get('X-Line-Signature', '')
    
    # Get request body
    body = request.get_data(as_text=True)
    logger.info("LINE webhook request body: " + body)
    
    # Verify signature
    if not verify_signature(body, signature):
        logger.error("Invalid signature")
        abort(400)
    
    # Parse request
    try:
        events = json.loads(body).get('events', [])
        for event in events:
            if event['type'] == 'message' and event['message']['type'] == 'text':
                handle_text_message(event)
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        abort(500)
    
    return 'OK', 200

def verify_signature(body, signature):
    """Verify LINE webhook signature"""
    if not LINE_CHANNEL_SECRET:
        return False
    
    hash = hmac.new(
        LINE_CHANNEL_SECRET.encode('utf-8'),
        body.encode('utf-8'),
        hashlib.sha256
    ).digest()
    
    return signature == base64.b64encode(hash).decode('utf-8')

def handle_text_message(event):
    """Handle LINE text messages"""
    try:
        # Get user message
        user_message = event['message']['text']
        reply_token = event['replyToken']
        
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
        reply_message(reply_token, response)
    
    except Exception as e:
        logger.error(f"Error handling LINE message: {str(e)}")
        reply_message(event['replyToken'], "エラーが発生しました。しばらくしてから再度お試しください。")

def reply_message(reply_token, text):
    """Send reply message to LINE"""
    if not LINE_CHANNEL_ACCESS_TOKEN:
        logger.error("LINE_CHANNEL_ACCESS_TOKEN not set")
        return
    
    url = 'https://api.line.me/v2/bot/message/reply'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
    }
    
    data = {
        'replyToken': reply_token,
        'messages': [{
            'type': 'text',
            'text': text
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            logger.error(f"LINE API error: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error sending LINE message: {str(e)}")