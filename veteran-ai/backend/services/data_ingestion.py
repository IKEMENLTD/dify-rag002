from typing import List, Dict, Any
from database.connection import supabase
from database.models import ChatMessage, Document, DocumentType
from integrations.slack_client import slack_client
from integrations.chatwork_client import chatwork_client
from integrations.line_client import line_client
from services.embedding_service import embedding_service
from services.text_processor import text_processor
import asyncio
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DataIngestionService:
    def __init__(self):
        pass
    
    async def sync_all_chat_platforms(self, hours_back: int = 24) -> Dict[str, int]:
        """Sync data from all configured chat platforms"""
        results = {
            "slack": 0,
            "chatwork": 0,
            "line": 0,
            "total": 0
        }
        
        # Sync Slack
        try:
            slack_messages = await slack_client.sync_all_channels(hours_back)
            slack_count = await self._process_chat_messages(slack_messages)
            results["slack"] = slack_count
        except Exception as e:
            print(f"Slack sync error: {e}")
        
        # Sync Chatwork
        try:
            chatwork_messages = await chatwork_client.sync_all_rooms()
            chatwork_count = await self._process_chat_messages(chatwork_messages)
            results["chatwork"] = chatwork_count
        except Exception as e:
            print(f"Chatwork sync error: {e}")
        
        # LINE messages are handled via webhook, so we don't sync them here
        
        results["total"] = results["slack"] + results["chatwork"] + results["line"]
        return results
    
    async def _process_chat_messages(self, messages: List[ChatMessage]) -> int:
        """Process and store chat messages"""
        processed_count = 0
        
        for message in messages:
            try:
                # Skip empty messages
                if not message.message.strip():
                    continue
                
                # Check if message already exists
                existing = supabase.table("chat_messages").select("id").eq(
                    "platform", message.platform.value
                ).eq(
                    "channel_id", message.channel_id
                ).eq(
                    "user_id", message.user_id
                ).eq(
                    "timestamp", message.timestamp.isoformat()
                ).execute()
                
                if existing.data:
                    continue  # Message already exists
                
                # Store chat message
                chat_data = {
                    "platform": message.platform.value,
                    "channel_id": message.channel_id,
                    "channel_name": message.channel_name,
                    "user_id": message.user_id,
                    "user_name": message.user_name,
                    "message": message.message,
                    "timestamp": message.timestamp.isoformat(),
                    "thread_ts": message.thread_ts,
                    "metadata": message.metadata
                }
                
                supabase.table("chat_messages").insert(chat_data).execute()
                
                # Create document for vector search
                await self._create_document_from_chat(message)
                processed_count += 1
                
            except Exception as e:
                print(f"Error processing chat message: {e}")
                continue
        
        return processed_count
    
    async def _create_document_from_chat(self, message: ChatMessage):
        """Create a searchable document from chat message"""
        try:
            # Process and clean text
            processed_text = await text_processor.process_chat_message(message.message)
            
            if not processed_text.strip():
                return
            
            # Create title
            title = f"{message.platform.value.title()} - {message.channel_name} - {message.user_name}"
            
            # Create embedding
            embedding = await embedding_service.create_embedding(processed_text)
            
            # Prepare document data
            document_data = {
                "title": title,
                "content": processed_text,
                "document_type": DocumentType.CHAT.value,
                "platform": message.platform.value,
                "embedding": embedding,
                "metadata": {
                    "channel_id": message.channel_id,
                    "channel_name": message.channel_name,
                    "user_id": message.user_id,
                    "user_name": message.user_name,
                    "timestamp": message.timestamp.isoformat(),
                    "thread_ts": message.thread_ts,
                    "original_metadata": message.metadata
                }
            }
            
            # Insert document
            supabase.table("documents").insert(document_data).execute()
            
        except Exception as e:
            print(f"Error creating document from chat: {e}")
    
    async def process_uploaded_file(self, file_data: Dict[str, Any]) -> bool:
        """Process an uploaded file and create searchable document"""
        try:
            file_path = file_data["file_path"]
            file_type = file_data["file_type"]
            filename = file_data["filename"]
            
            # Process file based on type
            content = ""
            if file_type.startswith("image/"):
                content = await text_processor.process_image(file_path)
                doc_type = DocumentType.IMAGE
            elif file_type == "application/pdf":
                content = await text_processor.process_pdf(file_path)
                doc_type = DocumentType.PDF
            elif file_type.startswith("audio/"):
                content = await text_processor.process_audio(file_path)
                doc_type = DocumentType.AUDIO
            else:
                content = await text_processor.process_text_file(file_path)
                doc_type = DocumentType.TEXT
            
            if not content.strip():
                return False
            
            # Create embedding
            embedding = await embedding_service.create_embedding(content)
            
            # Create document
            document_data = {
                "title": filename,
                "content": content,
                "document_type": doc_type.value,
                "embedding": embedding,
                "metadata": {
                    "file_path": file_path,
                    "file_type": file_type,
                    "file_size": file_data.get("file_size", 0),
                    "upload_timestamp": datetime.now().isoformat()
                }
            }
            
            result = supabase.table("documents").insert(document_data).execute()
            
            # Update file upload record with document ID
            if result.data:
                document_id = result.data[0]["id"]
                supabase.table("file_uploads").update({
                    "document_id": document_id,
                    "status": "completed"
                }).eq("filename", filename).execute()
            
            return True
            
        except Exception as e:
            print(f"Error processing uploaded file: {e}")
            # Update file upload status to failed
            supabase.table("file_uploads").update({
                "status": "failed"
            }).eq("filename", filename).execute()
            return False
    
    async def sync_periodic(self):
        """Periodic sync task (can be called by scheduler)"""
        print("Starting periodic sync...")
        results = await self.sync_all_chat_platforms(hours_back=1)  # Sync last hour
        print(f"Periodic sync completed: {results}")
        return results

# Global instance
data_ingestion_service = DataIngestionService()