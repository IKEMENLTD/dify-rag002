from supabase import create_client, Client
from core.config import settings
import asyncio

# Supabase client
supabase: Client = create_client(settings.supabase_url, settings.supabase_key)

async def init_db():
    """Initialize database tables and extensions"""
    try:
        # Test basic connection
        result = supabase.table("documents").select("count").limit(1).execute()
        
        # Try to enable pgvector extension
        try:
            supabase.rpc("enable_pgvector").execute()
        except Exception as ext_error:
            print(f"pgvector extension note: {ext_error}")
            # Continue - extension might already be enabled
        
        print("Database initialized successfully")
        
    except Exception as e:
        print(f"Database initialization error: {e}")
        # Don't fail startup if DB is temporarily unavailable
        pass

async def test_connection():
    """Test database connection"""
    try:
        result = supabase.table("documents").select("count").execute()
        print("Database connection successful")
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False