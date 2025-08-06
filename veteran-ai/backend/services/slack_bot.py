from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from fastapi import Request
from core.config import settings
from services.rag_engine import rag_engine
from database.models import ChatRequest
import re

# Initialize Slack Bolt app
app = AsyncApp(
    token=settings.slack_bot_token,
    signing_secret=settings.slack_signing_secret
)

# Create FastAPI handler
handler = AsyncSlackRequestHandler(app)

@app.event("app_mention")
async def handle_app_mention(event, say):
    """Handle app mentions in channels"""
    try:
        # Extract message text (remove mention)
        text = event.get("text", "")
        # Remove bot mention from text
        cleaned_text = re.sub(r'<@[A-Z0-9]+>', '', text).strip()
        
        if not cleaned_text:
            await say("何かご質問はありますか？")
            return
        
        # Generate response using RAG
        chat_request = ChatRequest(
            message=cleaned_text,
            context={
                "platform": "slack",
                "channel_id": event.get("channel"),
                "user_id": event.get("user"),
                "thread_ts": event.get("ts")
            }
        )
        
        response = await rag_engine.generate_response(chat_request)
        
        # Format response with sources
        reply_text = response.response
        
        if response.sources:
            reply_text += "\n\n📚 *参考情報:*"
            for i, source in enumerate(response.sources[:3], 1):
                reply_text += f"\n{i}. {source.title}"
                platform_info = f" ({source.platform})" if source.platform else ""
                reply_text += platform_info
        
        await say(
            text=reply_text,
            thread_ts=event.get("ts")
        )
        
    except Exception as e:
        print(f"App mention error: {e}")
        await say(
            "申し訳ございません。エラーが発生しました。しばらく後にお試しください。",
            thread_ts=event.get("ts")
        )

@app.event("message")
async def handle_direct_message(event, say):
    """Handle direct messages"""
    try:
        # Only handle direct messages (not in channels)
        if event.get("channel_type") != "im":
            return
        
        # Skip bot messages
        if event.get("subtype") == "bot_message" or event.get("bot_id"):
            return
        
        text = event.get("text", "")
        if not text.strip():
            return
        
        # Generate response using RAG
        chat_request = ChatRequest(
            message=text,
            context={
                "platform": "slack",
                "channel_id": event.get("channel"),
                "user_id": event.get("user"),
                "type": "direct_message"
            }
        )
        
        response = await rag_engine.generate_response(chat_request)
        
        # Format response with sources
        reply_text = response.response
        
        if response.sources:
            reply_text += "\n\n📚 *参考情報:*"
            for i, source in enumerate(response.sources[:3], 1):
                reply_text += f"\n{i}. {source.title}"
                platform_info = f" ({source.platform})" if source.platform else ""
                reply_text += platform_info
        
        await say(reply_text)
        
    except Exception as e:
        print(f"Direct message error: {e}")
        await say("申し訳ございません。エラーが発生しました。しばらく後にお試しください。")

@app.command("/veteran")
async def handle_slash_command(ack, respond, command):
    """Handle /veteran slash command"""
    try:
        await ack()
        
        text = command.get("text", "")
        if not text.strip():
            await respond("使用方法: `/veteran [質問]`\n例: `/veteran 最新のプロジェクト情報を教えて`")
            return
        
        # Generate response using RAG
        chat_request = ChatRequest(
            message=text,
            context={
                "platform": "slack",
                "channel_id": command.get("channel_id"),
                "user_id": command.get("user_id"),
                "type": "slash_command"
            }
        )
        
        response = await rag_engine.generate_response(chat_request)
        
        # Format response with sources
        reply_text = response.response
        
        if response.sources:
            reply_text += "\n\n📚 *参考情報:*"
            for i, source in enumerate(response.sources[:3], 1):
                reply_text += f"\n{i}. {source.title}"
                platform_info = f" ({source.platform})" if source.platform else ""
                reply_text += platform_info
        
        await respond(reply_text)
        
    except Exception as e:
        print(f"Slash command error: {e}")
        await respond("申し訳ございません。エラーが発生しました。しばらく後にお試しください。")

@app.action("search_similar")
async def handle_search_similar(ack, body, respond):
    """Handle search similar button action"""
    try:
        await ack()
        
        # Extract search query from action
        value = body.get("actions", [{}])[0].get("value", "")
        
        if not value:
            await respond("検索クエリが見つかりません。")
            return
        
        # Generate response using RAG
        chat_request = ChatRequest(
            message=f"「{value}」に関連する情報を検索して",
            context={
                "platform": "slack",
                "type": "button_action"
            }
        )
        
        response = await rag_engine.generate_response(chat_request)
        
        # Format response
        reply_text = f"「{value}」の検索結果:\n\n{response.response}"
        
        if response.sources:
            reply_text += "\n\n📚 *参考情報:*"
            for i, source in enumerate(response.sources[:3], 1):
                reply_text += f"\n{i}. {source.title}"
        
        await respond(reply_text)
        
    except Exception as e:
        print(f"Search similar action error: {e}")
        await respond("検索中にエラーが発生しました。")

# FastAPI route handler
async def slack_events_handler(request: Request):
    """Handle Slack events for FastAPI"""
    return await handler.handle(request)

# Export the Slack app and handler
slack_app = app
slack_handler = handler