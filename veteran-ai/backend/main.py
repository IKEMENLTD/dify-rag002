from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv

from routers import chat, search, upload, integrations
from database import init_db
from core.config import settings
from services.slack_bot import slack_handler
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.debug else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title="ベテランAI - Enterprise Knowledge AI System",
    description="社内非構造情報を統合・即時検索可能な生成AIナレッジ支援システム",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    await init_db()

# Include routers
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(upload.router, prefix="/api/upload", tags=["upload"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["integrations"])

# Slack bot endpoint
@app.post("/slack/events")
async def slack_events(request):
    return await slack_handler.handle(request)

@app.get("/")
async def root():
    return {
        "message": "ベテランAI - Enterprise Knowledge AI System",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=int(os.getenv("PORT", 8000)),
        reload=True if os.getenv("DEBUG", "false").lower() == "true" else False
    )