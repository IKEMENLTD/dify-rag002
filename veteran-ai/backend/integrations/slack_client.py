from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from core.config import settings
from database.models import ChatMessage, ChatPlatform
import asyncio
import time

class SlackClient:
    def __init__(self):
        self.client = WebClient(token=settings.slack_bot_token)
        self.platform = ChatPlatform.SLACK
    
    async def get_channels(self) -> List[Dict[str, Any]]:
        """Get list of channels the bot has access to"""
        try:
            response = self.client.conversations_list(
                types="public_channel,private_channel",
                exclude_archived=True
            )
            
            channels = []
            for channel in response["channels"]:
                channels.append({
                    "id": channel["id"],
                    "name": channel["name"],
                    "is_private": channel.get("is_private", False),
                    "member_count": channel.get("num_members", 0)
                })
            
            return channels
            
        except SlackApiError as e:
            print(f"Slack API error getting channels: {e}")
            return []
    
    async def get_channel_history(
        self, 
        channel_id: str, 
        hours_back: int = 24, 
        limit: int = 1000
    ) -> List[ChatMessage]:
        """Get message history from a channel"""
        try:
            # Calculate timestamp for hours_back
            oldest = (datetime.now() - timedelta(hours=hours_back)).timestamp()
            
            response = self.client.conversations_history(
                channel=channel_id,
                oldest=oldest,
                limit=limit
            )
            
            messages = []
            channel_info = await self._get_channel_info(channel_id)
            channel_name = channel_info.get("name", channel_id)
            
            for msg in response["messages"]:
                # Skip bot messages and system messages
                if msg.get("subtype") in ["bot_message", "channel_join", "channel_leave"]:
                    continue
                
                # Get user info
                user_info = await self._get_user_info(msg.get("user", ""))
                
                chat_message = ChatMessage(
                    platform=self.platform,
                    channel_id=channel_id,
                    channel_name=channel_name,
                    user_id=msg.get("user", ""),
                    user_name=user_info.get("real_name", user_info.get("name", "Unknown")),
                    message=msg.get("text", ""),
                    timestamp=datetime.fromtimestamp(float(msg.get("ts", 0))),
                    thread_ts=msg.get("thread_ts"),
                    metadata={
                        "ts": msg.get("ts"),
                        "client_msg_id": msg.get("client_msg_id"),
                        "reactions": msg.get("reactions", []),
                        "reply_count": msg.get("reply_count", 0)
                    }
                )
                messages.append(chat_message)
            
            return messages
            
        except SlackApiError as e:
            print(f"Slack API error getting channel history: {e}")
            return []
    
    async def get_thread_replies(self, channel_id: str, thread_ts: str) -> List[ChatMessage]:
        """Get replies in a specific thread"""
        try:
            response = self.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts
            )
            
            messages = []
            channel_info = await self._get_channel_info(channel_id)
            channel_name = channel_info.get("name", channel_id)
            
            for msg in response["messages"][1:]:  # Skip the parent message
                user_info = await self._get_user_info(msg.get("user", ""))
                
                chat_message = ChatMessage(
                    platform=self.platform,
                    channel_id=channel_id,
                    channel_name=channel_name,
                    user_id=msg.get("user", ""),
                    user_name=user_info.get("real_name", user_info.get("name", "Unknown")),
                    message=msg.get("text", ""),
                    timestamp=datetime.fromtimestamp(float(msg.get("ts", 0))),
                    thread_ts=thread_ts,
                    metadata={
                        "ts": msg.get("ts"),
                        "parent_user_id": response["messages"][0].get("user"),
                        "is_reply": True
                    }
                )
                messages.append(chat_message)
            
            return messages
            
        except SlackApiError as e:
            print(f"Slack API error getting thread replies: {e}")
            return []
    
    async def send_message(self, channel_id: str, text: str, thread_ts: Optional[str] = None) -> bool:
        """Send a message to a channel"""
        try:
            self.client.chat_postMessage(
                channel=channel_id,
                text=text,
                thread_ts=thread_ts
            )
            return True
            
        except SlackApiError as e:
            print(f"Slack API error sending message: {e}")
            return False
    
    async def send_rich_message(
        self, 
        channel_id: str, 
        text: str, 
        sources: List[Dict[str, Any]], 
        thread_ts: Optional[str] = None
    ) -> bool:
        """Send a rich message with source attachments"""
        try:
            # Build blocks for rich formatting
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": text
                    }
                }
            ]
            
            # Add sources as attachments
            if sources:
                blocks.append({
                    "type": "divider"
                })
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*参考情報:*"
                    }
                })
                
                for i, source in enumerate(sources[:3]):  # Limit to 3 sources
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{i+1}.* {source.get('title', 'Unknown')}\n_{source.get('content', '')[:100]}..._"
                        }
                    })
            
            self.client.chat_postMessage(
                channel=channel_id,
                blocks=blocks,
                thread_ts=thread_ts
            )
            return True
            
        except SlackApiError as e:
            print(f"Slack API error sending rich message: {e}")
            return False
    
    async def _get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """Get channel information (cached)"""
        try:
            response = self.client.conversations_info(channel=channel_id)
            return response["channel"]
        except SlackApiError:
            return {"name": channel_id}
    
    async def _get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get user information (cached)"""
        if not user_id:
            return {"name": "Unknown", "real_name": "Unknown"}
        
        try:
            response = self.client.users_info(user=user_id)
            return response["user"]
        except SlackApiError:
            return {"name": user_id, "real_name": user_id}
    
    async def sync_all_channels(self, hours_back: int = 24) -> List[ChatMessage]:
        """Sync messages from all accessible channels"""
        all_messages = []
        
        channels = await self.get_channels()
        
        for channel in channels:
            print(f"Syncing channel: {channel['name']}")
            messages = await self.get_channel_history(
                channel["id"], 
                hours_back=hours_back
            )
            all_messages.extend(messages)
            
            # Rate limiting - Slack has tier limits
            await asyncio.sleep(1)
        
        return all_messages

# Global instance
slack_client = SlackClient()