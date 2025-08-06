from openai import AsyncOpenAI
import anthropic
from typing import List, Dict, Any, Optional
from database.models import SearchResult, ChatRequest, ChatResponse
from services.vector_search import vector_search_service
from core.config import settings
import uuid
import json
import logging

logger = logging.getLogger(__name__)

class RAGEngine:
    def __init__(self):
        # Initialize LLM clients
        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        
        # RAG settings
        self.max_context_length = 4000
        self.max_sources = 5
        
    async def generate_response(self, request: ChatRequest) -> ChatResponse:
        """Generate response using RAG approach"""
        try:
            # Search for relevant documents
            search_results = await vector_search_service.search_by_text(
                request.message, 
                limit=self.max_sources
            )
            
            # Generate response using LLM
            response_text = await self._generate_llm_response(
                request.message, 
                search_results, 
                request.context
            )
            
            # Create conversation ID if not provided
            conversation_id = request.conversation_id or str(uuid.uuid4())
            
            return ChatResponse(
                response=response_text,
                conversation_id=conversation_id,
                sources=search_results,
                metadata={
                    "model_used": "gpt-4",
                    "search_results_count": len(search_results),
                    "context_length": len(self._build_context(search_results))
                }
            )
            
        except Exception as e:
            print(f"RAG response generation error: {e}")
            return ChatResponse(
                response="申し訳ございませんが、現在回答を生成できません。しばらく後にお試しください。",
                conversation_id=request.conversation_id or str(uuid.uuid4()),
                sources=[],
                metadata={"error": str(e)}
            )
    
    async def _generate_llm_response(
        self, 
        query: str, 
        sources: List[SearchResult], 
        context: Dict[str, Any]
    ) -> str:
        """Generate response using LLM with context"""
        
        # Build context from search results
        context_text = self._build_context(sources)
        
        # Create system prompt
        system_prompt = self._create_system_prompt()
        
        # Create user prompt with context
        user_prompt = self._create_user_prompt(query, context_text)
        
        try:
            # Use GPT-4 as primary LLM
            response = await self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as openai_error:
            print(f"OpenAI error: {openai_error}")
            
            # Fallback to Claude
            try:
                message = await self.anthropic_client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=1000,
                    temperature=0.7,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ]
                )
                
                return message.content[0].text
                
            except Exception as claude_error:
                print(f"Claude error: {claude_error}")
                raise Exception("All LLM providers failed")
    
    def _build_context(self, sources: List[SearchResult]) -> str:
        """Build context text from search results"""
        if not sources:
            return "関連する情報が見つかりませんでした。"
        
        context_parts = []
        current_length = 0
        
        for i, source in enumerate(sources):
            source_text = f"参考情報{i+1}:\n"
            source_text += f"タイトル: {source.title}\n"
            source_text += f"内容: {source.content[:500]}...\n"
            source_text += f"プラットフォーム: {source.platform or 'ファイル'}\n"
            source_text += f"作成日時: {source.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            
            if current_length + len(source_text) > self.max_context_length:
                break
            
            context_parts.append(source_text)
            current_length += len(source_text)
        
        return "".join(context_parts)
    
    def _create_system_prompt(self) -> str:
        """Create system prompt for LLM"""
        return """あなたは「ベテランAI」という企業内ナレッジ支援システムのAIアシスタントです。

役割:
- 社内の様々な情報源（チャット履歴、文書、画像、音声記録等）から関連情報を検索し、正確で有用な回答を提供する
- 提供された参考情報に基づいて回答し、情報源を明確に示す
- 日本語で自然で分かりやすい回答をする

回答時の注意点:
1. 提供された参考情報を基に回答してください
2. 情報源が不明確な場合は、その旨を明記してください
3. 専門的な内容は分かりやすく説明してください
4. 関連する参考情報がある場合は、それらを含めて包括的に回答してください
5. 不正確な情報や推測に基づく回答は避けてください

回答形式:
- 直接的で簡潔な回答から始める
- 必要に応じて詳細説明を追加
- 参考にした情報源について言及する"""

    def _create_user_prompt(self, query: str, context: str) -> str:
        """Create user prompt with query and context"""
        return f"""質問: {query}

以下は社内システムから検索された関連情報です:

{context}

上記の参考情報を基に、質問に対して正確で有用な回答を日本語で提供してください。参考情報に基づかない推測は避け、情報源を適切に参照してください。"""

    async def generate_summary(self, documents: List[SearchResult]) -> str:
        """Generate summary of multiple documents"""
        try:
            context = self._build_context(documents)
            
            prompt = f"""以下の文書群について、重要なポイントを整理して要約してください:

{context}

要約時の注意点:
- 主要なポイントを箇条書きで整理
- 日付や数値などの具体的な情報を含める
- 文書間の関連性があれば言及する
- 200-300文字程度で簡潔にまとめる"""

            response = await self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "あなたは文書要約の専門家です。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Summary generation error: {e}")
            return "要約の生成中にエラーが発生しました。"

# Global instance
rag_engine = RAGEngine()