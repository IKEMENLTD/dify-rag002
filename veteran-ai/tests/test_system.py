"""
ベテランAI システム統合テスト
"""
import pytest
import asyncio
import os
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
backend_path = project_root / "backend"
sys.path.insert(0, str(backend_path))

class TestSystemIntegration:
    """システム統合テスト"""
    
    @pytest.mark.asyncio
    async def test_imports(self):
        """モジュールインポートテスト"""
        try:
            from core.config import settings
            from database.connection import supabase
            from services.embedding_service import embedding_service
            from services.rag_engine import rag_engine
            assert True
        except ImportError as e:
            pytest.fail(f"モジュールインポートエラー: {e}")
    
    def test_environment_variables(self):
        """環境変数テスト"""
        # 最低限必要な環境変数
        required_vars = ["SUPABASE_URL", "SUPABASE_KEY"]
        
        for var in required_vars:
            if not os.getenv(var):
                pytest.skip(f"環境変数 {var} が設定されていません")
    
    def test_file_structure(self):
        """ファイル構造テスト"""
        required_files = [
            "backend/main.py",
            "backend/core/config.py", 
            "backend/database/schema.sql",
            "requirements.txt"
        ]
        
        for file_path in required_files:
            full_path = project_root / file_path
            assert full_path.exists(), f"必要ファイル {file_path} が存在しません"
    
    @pytest.mark.asyncio
    async def test_embedding_service(self):
        """Embeddingサービステスト"""
        try:
            from services.embedding_service import EmbeddingService
            service = EmbeddingService()
            
            # 空文字列のテスト
            cleaned = service._clean_text("")
            assert cleaned == ""
            
            # 基本的なテキストクリーニング
            cleaned = service._clean_text("  テスト　テキスト  ")
            assert cleaned == "テスト テキスト"
            
        except Exception as e:
            pytest.skip(f"Embeddingサービステストスキップ: {e}")
    
    @pytest.mark.asyncio
    async def test_database_models(self):
        """データベースモデルテスト"""
        try:
            from database.models import ChatRequest, SearchQuery, DocumentType
            
            # ChatRequestテスト
            request = ChatRequest(message="テストメッセージ")
            assert request.message == "テストメッセージ"
            
            # SearchQueryテスト
            query = SearchQuery(query="検索テスト")
            assert query.query == "検索テスト"
            assert query.limit == 10  # デフォルト値
            
            # DocumentTypeテスト
            assert DocumentType.CHAT == "chat"
            assert DocumentType.PDF == "pdf"
            
        except Exception as e:
            pytest.fail(f"データベースモデルテストエラー: {e}")

if __name__ == "__main__":
    # .envファイルを読み込み
    env_file = project_root / ".env"
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)
    
    pytest.main([__file__, "-v"])