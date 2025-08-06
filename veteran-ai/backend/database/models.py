from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class DocumentType(str, Enum):
    CHAT = "chat"
    PDF = "pdf"
    IMAGE = "image"
    AUDIO = "audio"
    TEXT = "text"

class ChatPlatform(str, Enum):
    SLACK = "slack"
    LINE = "line"
    CHATWORK = "chatwork"

class Document(BaseModel):
    id: Optional[str] = None
    title: str
    content: str
    document_type: DocumentType
    platform: Optional[ChatPlatform] = None
    metadata: Dict[str, Any] = {}
    embedding: Optional[List[float]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ChatMessage(BaseModel):
    id: Optional[str] = None
    platform: ChatPlatform
    channel_id: str
    channel_name: str
    user_id: str
    user_name: str
    message: str
    timestamp: datetime
    thread_ts: Optional[str] = None
    metadata: Dict[str, Any] = {}

class SearchQuery(BaseModel):
    query: str
    limit: int = Field(default=10, ge=1, le=50)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    document_types: Optional[List[DocumentType]] = None
    platforms: Optional[List[ChatPlatform]] = None

class SearchResult(BaseModel):
    id: str
    title: str
    content: str
    document_type: DocumentType
    platform: Optional[ChatPlatform]
    similarity_score: float
    metadata: Dict[str, Any]
    created_at: datetime

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = {}

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    sources: List[SearchResult]
    metadata: Dict[str, Any] = {}

class FileUpload(BaseModel):
    filename: str
    file_type: str
    title: Optional[str] = None
    metadata: Dict[str, Any] = {}