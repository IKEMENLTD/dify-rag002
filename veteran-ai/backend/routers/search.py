from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from database.models import SearchQuery, SearchResult, DocumentType, ChatPlatform
from services.vector_search import vector_search_service
from services.rag_engine import rag_engine

router = APIRouter()

@router.post("/", response_model=List[SearchResult])
async def search_documents(query: SearchQuery):
    """Search documents using vector similarity"""
    try:
        if not query.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        results = await vector_search_service.search(query)
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Search error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/", response_model=List[SearchResult])
async def search_simple(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    threshold: float = Query(0.7, ge=0.0, le=1.0, description="Similarity threshold"),
    doc_types: Optional[List[DocumentType]] = Query(None, description="Document types to filter"),
    platforms: Optional[List[ChatPlatform]] = Query(None, description="Platforms to filter")
):
    """Simple search endpoint with URL parameters"""
    try:
        query = SearchQuery(
            query=q,
            limit=limit,
            similarity_threshold=threshold,
            document_types=doc_types,
            platforms=platforms
        )
        
        results = await vector_search_service.search(query)
        return results
        
    except Exception as e:
        print(f"Simple search error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/similar/{document_id}", response_model=List[SearchResult])
async def find_similar_documents(
    document_id: str,
    limit: int = Query(5, ge=1, le=20, description="Number of similar documents")
):
    """Find documents similar to the given document"""
    try:
        results = await vector_search_service.get_similar_documents(document_id, limit)
        return results
        
    except Exception as e:
        print(f"Similar documents error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/summarize")
async def summarize_search_results(query: SearchQuery):
    """Search and summarize results"""
    try:
        if not query.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        # Get search results
        results = await vector_search_service.search(query)
        
        if not results:
            return {
                "summary": "検索クエリに関連する情報が見つかりませんでした。",
                "results": [],
                "query": query.query
            }
        
        # Generate summary
        summary = await rag_engine.generate_summary(results)
        
        return {
            "summary": summary,
            "results": results,
            "query": query.query
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Summarize error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/stats")
async def get_search_stats():
    """Get search and document statistics"""
    try:
        from database.connection import supabase
        
        # Get document counts by type
        doc_stats = supabase.table("documents").select("document_type").execute()
        
        type_counts = {}
        for doc in doc_stats.data:
            doc_type = doc["document_type"]
            type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
        
        # Get platform counts
        platform_stats = supabase.table("documents").select("platform").execute()
        
        platform_counts = {}
        for doc in platform_stats.data:
            platform = doc["platform"] or "file"
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        # Get total counts
        total_docs = len(doc_stats.data)
        
        return {
            "total_documents": total_docs,
            "by_type": type_counts,
            "by_platform": platform_counts
        }
        
    except Exception as e:
        print(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")