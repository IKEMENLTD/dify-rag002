from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from typing import Dict, Any
from integrations.slack_client import slack_client
from integrations.chatwork_client import chatwork_client
from integrations.line_client import line_client
from services.data_ingestion import data_ingestion_service
from services.rag_engine import rag_engine
from database.models import ChatRequest
import json
import hmac
import hashlib

router = APIRouter()

@router.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    """Handle Slack events and mentions"""
    try:
        body = await request.body()
        
        # Parse JSON
        data = json.loads(body)
        
        # Handle URL verification
        if data.get("type") == "url_verification":
            return {"challenge": data["challenge"]}
        
        # Handle events
        if data.get("type") == "event_callback":
            event = data.get("event", {})
            
            # Handle app mentions
            if event.get("type") == "app_mention":
                background_tasks.add_task(handle_slack_mention, event)
            
            # Handle direct messages
            elif event.get("type") == "message" and event.get("channel_type") == "im":
                background_tasks.add_task(handle_slack_dm, event)
        
        return {"status": "ok"}
        
    except Exception as e:
        print(f"Slack events error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/line/webhook")
async def line_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle LINE webhook events"""
    try:
        body = await request.body()
        signature = request.headers.get("x-line-signature", "")
        
        # Verify signature
        if not line_client.verify_signature(body, signature):
            raise HTTPException(status_code=403, detail="Invalid signature")
        
        # Parse events
        data = json.loads(body)
        
        for event in data.get("events", []):
            if event.get("type") == "message":
                background_tasks.add_task(handle_line_message, event)
        
        return {"status": "ok"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"LINE webhook error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/sync")
async def sync_chat_platforms(background_tasks: BackgroundTasks, hours_back: int = 24):
    """Manually trigger sync of all chat platforms"""
    try:
        background_tasks.add_task(sync_platforms_background, hours_back)
        
        return {
            "message": "Sync started",
            "hours_back": hours_back
        }
        
    except Exception as e:
        print(f"Sync trigger error: {e}")
        raise HTTPException(status_code=500, detail="Failed to start sync")

@router.get("/slack/channels")
async def get_slack_channels():
    """Get list of Slack channels"""
    try:
        channels = await slack_client.get_channels()
        return {"channels": channels}
        
    except Exception as e:
        print(f"Get Slack channels error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get channels")

@router.get("/chatwork/rooms")
async def get_chatwork_rooms():
    """Get list of Chatwork rooms"""
    try:
        rooms = await chatwork_client.get_rooms()
        return {"rooms": rooms}
        
    except Exception as e:
        print(f"Get Chatwork rooms error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get rooms")

@router.get("/status")
async def get_integration_status():
    """Get status of all integrations"""
    try:
        status = {
            "slack": False,
            "chatwork": False,
            "line": False
        }
        
        # Test Slack
        try:
            channels = await slack_client.get_channels()
            status["slack"] = len(channels) > 0
        except:
            pass
        
        # Test Chatwork
        try:
            rooms = await chatwork_client.get_rooms()
            status["chatwork"] = len(rooms) > 0
        except:
            pass
        
        # Test LINE
        try:
            bot_info = await line_client.get_bot_info()
            status["line"] = bool(bot_info)
        except:
            pass
        
        return status
        
    except Exception as e:
        print(f"Integration status error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get status")

async def handle_slack_mention(event: Dict[str, Any]):
    """Handle Slack app mention"""
    try:
        # Extract message text (remove mention)
        text = event.get("text", "")
        # Remove bot mention from text
        cleaned_text = text.split(">", 1)[-1].strip() if ">" in text else text
        
        if not cleaned_text:
            return
        
        # Generate response
        chat_request = ChatRequest(
            message=cleaned_text,
            context={
                "platform": "slack",
                "channel_id": event.get("channel"),
                "user_id": event.get("user")
            }
        )
        
        response = await rag_engine.generate_response(chat_request)
        
        # Send response to Slack
        await slack_client.send_rich_message(
            channel_id=event.get("channel"),
            text=response.response,
            sources=[source.dict() for source in response.sources],
            thread_ts=event.get("ts")
        )
        
    except Exception as e:
        print(f"Slack mention handling error: {e}")

async def handle_slack_dm(event: Dict[str, Any]):
    """Handle Slack direct message"""
    try:
        text = event.get("text", "")
        
        if not text.strip():
            return
        
        # Generate response
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
        
        # Send response to Slack
        await slack_client.send_rich_message(
            channel_id=event.get("channel"),
            text=response.response,
            sources=[source.dict() for source in response.sources]
        )
        
    except Exception as e:
        print(f"Slack DM handling error: {e}")

async def handle_line_message(event: Dict[str, Any]):
    """Handle LINE message"""
    try:
        if event.get("message", {}).get("type") != "text":
            return
        
        text = event.get("message", {}).get("text", "")
        
        if not text.strip():
            return
        
        # Generate response
        chat_request = ChatRequest(
            message=text,
            context={
                "platform": "line",
                "user_id": event.get("source", {}).get("userId"),
                "source": event.get("source", {})
            }
        )
        
        response = await rag_engine.generate_response(chat_request)
        
        # Send response to LINE
        await line_client.reply_rich_message(
            reply_token=event.get("replyToken"),
            text=response.response,
            sources=[source.dict() for source in response.sources]
        )
        
    except Exception as e:
        print(f"LINE message handling error: {e}")

async def sync_platforms_background(hours_back: int):
    """Background task to sync all platforms"""
    try:
        results = await data_ingestion_service.sync_all_chat_platforms(hours_back)
        print(f"Platform sync completed: {results}")
        
    except Exception as e:
        print(f"Background sync error: {e}")