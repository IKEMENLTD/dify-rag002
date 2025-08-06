import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.config import settings
from database.models import ChatMessage, ChatPlatform
import json

class LineClient:
    def __init__(self):
        self.channel_access_token = settings.line_channel_access_token
        self.channel_secret = settings.line_channel_secret
        self.base_url = "https://api.line.me/v2/bot"
        self.headers = {
            "Authorization": f"Bearer {self.channel_access_token}",
            "Content-Type": "application/json"
        }
        self.platform = ChatPlatform.LINE
    
    async def handle_webhook_event(self, event: Dict[str, Any]) -> Optional[ChatMessage]:
        """Handle incoming LINE webhook event"""
        try:
            if event.get("type") != "message" or event.get("message", {}).get("type") != "text":
                return None
            
            # Get user profile
            user_profile = await self._get_user_profile(event["source"]["userId"])
            
            chat_message = ChatMessage(
                platform=self.platform,
                channel_id=event["source"].get("groupId", event["source"].get("roomId", event["source"]["userId"])),
                channel_name=self._get_chat_name(event["source"]),
                user_id=event["source"]["userId"],
                user_name=user_profile.get("displayName", "Unknown"),
                message=event["message"]["text"],
                timestamp=datetime.fromtimestamp(event["timestamp"] / 1000),
                metadata={
                    "message_id": event["message"]["id"],
                    "reply_token": event["replyToken"],
                    "source_type": event["source"]["type"],
                    "user_picture": user_profile.get("pictureUrl")
                }
            )
            
            return chat_message
            
        except Exception as e:
            print(f"LINE webhook event handling error: {e}")
            return None
    
    async def reply_message(self, reply_token: str, message: str) -> bool:
        """Reply to a LINE message"""
        try:
            data = {
                "replyToken": reply_token,
                "messages": [
                    {
                        "type": "text",
                        "text": message
                    }
                ]
            }
            
            response = requests.post(
                f"{self.base_url}/message/reply",
                headers=self.headers,
                data=json.dumps(data)
            )
            response.raise_for_status()
            return True
            
        except requests.RequestException as e:
            print(f"LINE reply message error: {e}")
            return False
    
    async def reply_rich_message(
        self, 
        reply_token: str, 
        text: str, 
        sources: List[Dict[str, Any]]
    ) -> bool:
        """Reply with rich message including sources"""
        try:
            messages = [
                {
                    "type": "text",
                    "text": text
                }
            ]
            
            # Add sources as separate messages if available
            if sources:
                source_text = "=== 参考情報 ===\n"
                for i, source in enumerate(sources[:3]):
                    source_text += f"{i+1}. {source.get('title', 'Unknown')}\n"
                    source_text += f"{source.get('content', '')[:100]}...\n\n"
                
                messages.append({
                    "type": "text",
                    "text": source_text
                })
            
            data = {
                "replyToken": reply_token,
                "messages": messages
            }
            
            response = requests.post(
                f"{self.base_url}/message/reply",
                headers=self.headers,
                data=json.dumps(data)
            )
            response.raise_for_status()
            return True
            
        except requests.RequestException as e:
            print(f"LINE rich reply error: {e}")
            return False
    
    async def push_message(self, to: str, message: str) -> bool:
        """Push a message to user/group/room"""
        try:
            data = {
                "to": to,
                "messages": [
                    {
                        "type": "text",
                        "text": message
                    }
                ]
            }
            
            response = requests.post(
                f"{self.base_url}/message/push",
                headers=self.headers,
                data=json.dumps(data)
            )
            response.raise_for_status()
            return True
            
        except requests.RequestException as e:
            print(f"LINE push message error: {e}")
            return False
    
    async def _get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get user profile information"""
        try:
            response = requests.get(
                f"{self.base_url}/profile/{user_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException:
            return {"displayName": user_id}
    
    async def _get_group_summary(self, group_id: str) -> Dict[str, Any]:
        """Get group summary information"""
        try:
            response = requests.get(
                f"{self.base_url}/group/{group_id}/summary",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException:
            return {"groupName": group_id}
    
    def _get_chat_name(self, source: Dict[str, Any]) -> str:
        """Get chat name based on source type"""
        source_type = source.get("type", "user")
        
        if source_type == "group":
            return f"Group_{source.get('groupId', 'Unknown')}"
        elif source_type == "room":
            return f"Room_{source.get('roomId', 'Unknown')}"
        else:
            return f"Direct_{source.get('userId', 'Unknown')}"
    
    async def get_bot_info(self) -> Dict[str, Any]:
        """Get bot information"""
        try:
            response = requests.get(
                f"{self.base_url}/info",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            print(f"LINE bot info error: {e}")
            return {}
    
    def verify_signature(self, body: bytes, signature: str) -> bool:
        """Verify LINE webhook signature"""
        import hmac
        import hashlib
        import base64
        
        hash = hmac.new(
            self.channel_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).digest()
        
        expected_signature = base64.b64encode(hash).decode()
        return hmac.compare_digest(signature, expected_signature)

# Global instance
line_client = LineClient()