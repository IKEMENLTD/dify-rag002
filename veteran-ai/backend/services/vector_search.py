from typing import List, Optional, Dict, Any
from database.connection import supabase
from database.models import SearchQuery, SearchResult, DocumentType, ChatPlatform
from services.embedding_service import embedding_service
from datetime import datetime

class VectorSearchService:
    def __init__(self):
        self.table_name = "documents"
    
    async def search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform vector similarity search"""
        try:
            # Create embedding for the query
            query_embedding = await embedding_service.create_embedding(query.query)
            
            # Build the query
            db_query = supabase.table(self.table_name).select(
                "id, title, content, document_type, platform, metadata, created_at"
            )
            
            # Add filters
            if query.document_types:
                db_query = db_query.in_("document_type", [dt.value for dt in query.document_types])
            
            if query.platforms:
                db_query = db_query.in_("platform", [p.value for p in query.platforms])
            
            # Execute vector search using RPC function
            response = supabase.rpc(
                "vector_search",
                {
                    "query_embedding": query_embedding,
                    "similarity_threshold": query.similarity_threshold,
                    "match_count": query.limit
                }
            ).execute()
            
            # Process results
            results = []
            for item in response.data:
                result = SearchResult(
                    id=item["id"],
                    title=item["title"],
                    content=item["content"],
                    document_type=DocumentType(item["document_type"]),
                    platform=ChatPlatform(item["platform"]) if item["platform"] else None,
                    similarity_score=item.get("similarity", 0.0),
                    metadata=item.get("metadata", {}),
                    created_at=datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            print(f"Vector search error: {e}")
            return []
    
    async def search_by_text(self, text: str, limit: int = 10) -> List[SearchResult]:
        """Simple text-based vector search"""
        query = SearchQuery(query=text, limit=limit)
        return await self.search(query)
    
    async def get_similar_documents(self, document_id: str, limit: int = 5) -> List[SearchResult]:
        """Find similar documents to a given document"""
        try:
            # Get the document embedding
            doc_response = supabase.table(self.table_name).select(
                "embedding, title"
            ).eq("id", document_id).execute()
            
            if not doc_response.data:
                return []
            
            document_embedding = doc_response.data[0]["embedding"]
            
            # Search for similar documents
            response = supabase.rpc(
                "find_similar_documents",
                {
                    "target_embedding": document_embedding,
                    "exclude_id": document_id,
                    "match_count": limit
                }
            ).execute()
            
            # Process results
            results = []
            for item in response.data:
                result = SearchResult(
                    id=item["id"],
                    title=item["title"],
                    content=item["content"],
                    document_type=DocumentType(item["document_type"]),
                    platform=ChatPlatform(item["platform"]) if item["platform"] else None,
                    similarity_score=item.get("similarity", 0.0),
                    metadata=item.get("metadata", {}),
                    created_at=datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            print(f"Similar documents search error: {e}")
            return []

# Global instance
vector_search_service = VectorSearchService()