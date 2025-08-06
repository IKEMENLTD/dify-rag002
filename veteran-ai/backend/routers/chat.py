from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from database.models import ChatRequest, ChatResponse, SearchResult
from services.rag_engine import rag_engine
from database.connection import supabase
import uuid
from datetime import datetime

router = APIRouter()

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Generate response using RAG"""
    try:
        if not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        # Generate response using RAG engine
        response = await rag_engine.generate_response(request)
        
        # Store conversation in database
        await _store_conversation(request, response)
        
        return response
        
    except Exception as e:
        print(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation history"""
    try:
        # Get conversation
        conv_response = supabase.table("conversations").select("*").eq("id", conversation_id).execute()
        
        if not conv_response.data:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get messages
        messages_response = supabase.table("conversation_messages").select("*").eq(
            "conversation_id", conversation_id
        ).order("created_at").execute()
        
        return {
            "conversation": conv_response.data[0],
            "messages": messages_response.data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Get conversation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/conversations")
async def list_conversations(user_id: Optional[str] = None, limit: int = 50):
    """List recent conversations"""
    try:
        query = supabase.table("conversations").select("*").order("updated_at", desc=True).limit(limit)
        
        if user_id:
            query = query.eq("user_id", user_id)
        
        response = query.execute()
        return response.data
        
    except Exception as e:
        print(f"List conversations error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation"""
    try:
        # Delete conversation (messages will be deleted by cascade)
        response = supabase.table("conversations").delete().eq("id", conversation_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return {"message": "Conversation deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Delete conversation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

async def _store_conversation(request: ChatRequest, response: ChatResponse):
    """Store conversation in database"""
    try:
        conversation_id = response.conversation_id
        
        # Check if conversation exists
        conv_check = supabase.table("conversations").select("id").eq("id", conversation_id).execute()
        
        if not conv_check.data:
            # Create new conversation
            conv_data = {
                "id": conversation_id,
                "user_id": request.context.get("user_id"),
                "title": request.message[:50] + "..." if len(request.message) > 50 else request.message,
                "metadata": request.context
            }
            supabase.table("conversations").insert(conv_data).execute()
        
        # Store user message
        user_message = {
            "conversation_id": conversation_id,
            "role": "user",
            "content": request.message,
            "metadata": request.context
        }
        supabase.table("conversation_messages").insert(user_message).execute()
        
        # Store assistant response
        assistant_message = {
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": response.response,
            "sources": [source.dict() for source in response.sources],
            "metadata": response.metadata
        }
        supabase.table("conversation_messages").insert(assistant_message).execute()
        
        # Update conversation timestamp
        supabase.table("conversations").update({
            "updated_at": datetime.now().isoformat()
        }).eq("id", conversation_id).execute()
        
    except Exception as e:
        print(f"Store conversation error: {e}")
        # Don't raise error as this shouldn't break the main flow