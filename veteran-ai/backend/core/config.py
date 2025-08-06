from pydantic_settings import BaseSettings
from pydantic import Field
import os

class Settings(BaseSettings):
    # App Settings
    app_name: str = "ベテランAI"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    
    # Supabase Settings
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_KEY", "")
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    
    # AI Provider Settings
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    
    # Chat Integration Settings
    slack_bot_token: str = os.getenv("SLACK_BOT_TOKEN", "")
    slack_app_token: str = os.getenv("SLACK_APP_TOKEN", "")
    slack_signing_secret: str = os.getenv("SLACK_SIGNING_SECRET", "")
    
    line_channel_access_token: str = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_channel_secret: str = os.getenv("LINE_CHANNEL_SECRET", "")
    
    chatwork_api_token: str = os.getenv("CHATWORK_API_TOKEN", "")
    
    # Redis Settings
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # File Upload Settings
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    upload_dir: str = os.getenv("UPLOAD_DIR", "./uploads")
    
    # Embedding Settings
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    
    # Search Settings
    max_search_results: int = 10
    similarity_threshold: float = 0.7
    
    class Config:
        env_file = ".env"

settings = Settings()