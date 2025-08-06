from openai import AsyncOpenAI
from typing import List, Optional
from core.config import settings
import numpy as np
import logging

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions
    
    async def create_embedding(self, text: str) -> List[float]:
        """Create embedding for a single text"""
        try:
            # Clean and prepare text
            cleaned_text = self._clean_text(text)
            
            if not cleaned_text:
                logger.warning("Empty text provided for embedding")
                return [0.0] * self.dimensions
            
            response = await self.client.embeddings.create(
                model=self.model,
                input=cleaned_text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Embedding creation error: {e}")
            raise
    
    async def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Create embeddings for multiple texts"""
        try:
            # Clean texts
            cleaned_texts = [self._clean_text(text) for text in texts if self._clean_text(text)]
            
            if not cleaned_texts:
                logger.warning("No valid texts provided for batch embedding")
                return []
            
            response = await self.client.embeddings.create(
                model=self.model,
                input=cleaned_texts
            )
            
            return [item.embedding for item in response.data]
            
        except Exception as e:
            logger.error(f"Batch embedding creation error: {e}")
            raise
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for embedding"""
        if not text or not text.strip():
            return ""
        
        # Remove excessive whitespace
        cleaned = " ".join(text.split())
        
        # Truncate if too long (8191 tokens limit for OpenAI)
        if len(cleaned) > 8000:  # Conservative limit
            cleaned = cleaned[:8000] + "..."
        
        return cleaned
    
    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings"""
        try:
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            print(f"Similarity calculation error: {e}")
            return 0.0

# Global instance
embedding_service = EmbeddingService()