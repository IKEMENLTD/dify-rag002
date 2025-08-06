import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from core.config import settings
from database.models import ChatMessage, ChatPlatform
import asyncio

class ChatworkClient:
    def __init__(self):
        self.api_token = settings.chatwork_api_token
        self.base_url = "https://api.chatwork.com/v2"
        self.headers = {
            "X-ChatWorkToken": self.api_token,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        self.platform = ChatPlatform.CHATWORK
    
    async def get_rooms(self) -> List[Dict[str, Any]]:
        """Get list of rooms the user has access to"""
        try:
            response = requests.get(
                f"{self.base_url}/rooms",
                headers=self.headers
            )
            response.raise_for_status()
            
            rooms = []
            for room in response.json():
                rooms.append({
                    "id": str(room["room_id"]),
                    "name": room["name"],
                    "type": room["type"],
                    "member_count": room.get("member_count", 0),
                    "description": room.get("description", "")
                })
            
            return rooms
            
        except requests.RequestException as e:
            print(f"Chatwork API error getting rooms: {e}")
            return []
    
    async def get_room_messages(
        self, 
        room_id: str, 
        force: bool = False
    ) -> List[ChatMessage]:
        """Get messages from a room"""
        try:
            params = {}
            if force:
                params["force"] = "1"
            
            response = requests.get(
                f"{self.base_url}/rooms/{room_id}/messages",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            
            messages = []
            room_info = await self._get_room_info(room_id)
            room_name = room_info.get("name", room_id)
            
            for msg in response.json():
                chat_message = ChatMessage(
                    platform=self.platform,
                    channel_id=room_id,
                    channel_name=room_name,
                    user_id=str(msg["account"]["account_id"]),
                    user_name=msg["account"]["name"],
                    message=msg["body"],
                    timestamp=datetime.fromtimestamp(msg["send_time"]),
                    metadata={
                        "message_id": str(msg["message_id"]),
                        "update_time": msg.get("update_time"),
                        "account_avatar": msg["account"].get("avatar_image_url")
                    }
                )
                messages.append(chat_message)
            
            return messages
            
        except requests.RequestException as e:
            print(f"Chatwork API error getting room messages: {e}")
            return []
    
    async def send_message(self, room_id: str, message: str) -> bool:
        """Send a message to a room"""
        try:
            data = {"body": message}
            
            response = requests.post(
                f"{self.base_url}/rooms/{room_id}/messages",
                headers=self.headers,
                data=data
            )
            response.raise_for_status()
            return True
            
        except requests.RequestException as e:
            print(f"Chatwork API error sending message: {e}")
            return False
    
    async def send_rich_message(
        self, 
        room_id: str, 
        text: str, 
        sources: List[Dict[str, Any]]
    ) -> bool:
        """Send a rich message with source information"""
        try:
            # Build formatted message
            formatted_message = f"{text}\n\n"
            
            if sources:
                formatted_message += "=== 参考情報 ===\n"
                for i, source in enumerate(sources[:3]):
                    formatted_message += f"{i+1}. {source.get('title', 'Unknown')}\n"
                    formatted_message += f"   {source.get('content', '')[:100]}...\n\n"
            
            return await self.send_message(room_id, formatted_message)
            
        except Exception as e:
            print(f"Chatwork rich message error: {e}")
            return False
    
    async def get_me(self) -> Dict[str, Any]:
        """Get current user information"""
        try:
            response = requests.get(
                f"{self.base_url}/me",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            print(f"Chatwork API error getting user info: {e}")
            return {}
    
    async def _get_room_info(self, room_id: str) -> Dict[str, Any]:
        """Get room information"""
        try:
            response = requests.get(
                f"{self.base_url}/rooms/{room_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException:
            return {"name": room_id}
    
    async def sync_all_rooms(self) -> List[ChatMessage]:
        """Sync messages from all accessible rooms"""
        all_messages = []
        
        rooms = await self.get_rooms()
        
        for room in rooms:
            print(f"Syncing Chatwork room: {room['name']}")
            messages = await self.get_room_messages(room["id"])
            all_messages.extend(messages)
            
            # Rate limiting
            await asyncio.sleep(2)  # Chatwork has stricter rate limits
        
        return all_messages

# Global instance
chatwork_client = ChatworkClient()