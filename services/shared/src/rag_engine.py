"""
RAG Engine - Orchestrates the complete Retrieval Augmented Generation flow.

Combines query processing, vector retrieval, context assembly, and answer generation.
"""

from typing import Dict, List, Optional, Any, Iterator
from query_processor import QueryProcessor
from retrieval_service import RetrievalService, RetrievalResult
from bedrock_wrappers import invoke_model, invoke_model_streaming


class RAGEngine:
    """Main RAG orchestration engine."""

    def __init__(
        self,
        vectors_bucket: str,
        embedding_model_id: str = "amazon.titan-embed-text-v2:0",
        generation_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
        region: str = "us-east-1"
    ):
        """
        Initialize RAG engine.

        Args:
            vectors_bucket: S3 bucket containing vectors
            embedding_model_id: Model ID for embeddings
            generation_model_id: Model ID for answer generation
            region: AWS region
        """
        self.vectors_bucket = vectors_bucket
        self.embedding_model_id = embedding_model_id
        self.generation_model_id = generation_model_id
        self.region = region

        # Initialize services
        self.query_processor = QueryProcessor(
            embedding_model_id=embedding_model_id,
            region=region
        )
        self.retrieval_service = RetrievalService(
            vectors_bucket=vectors_bucket,
            region=region
        )

        # Initialize Bedrock client for generation
        import boto3
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=region)

    def query(
        self,
        question: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        include_citations: bool = True,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Process a RAG query and generate an answer.

        Args:
            question: User's question
            filters: Optional metadata filters
            top_k: Number of chunks to retrieve
            include_citations: Whether to include citations
            stream: Whether to stream the response

        Returns:
            Dict containing answer, citations, and metadata
        """
        # Step 1: Process query
        processed_query = self.query_processor.process_query(
            query=question,
            filters=filters,
            top_k=top_k
        )

        # Step 2: Retrieve relevant chunks
        results = self.retrieval_service.retrieve_with_reranking(
            query_embedding=processed_query['embedding'],
            query_text=processed_query['normalized_query'],
            top_k=top_k,
            filters=processed_query['filters']
        )

        # Step 3: Assemble context
        context = self.retrieval_service.get_context_window(
            results=results,
            max_tokens=4000
        )

        # Step 4: Generate answer
        if stream:
            # For streaming, we'll return a generator
            return self._generate_streaming_answer(
                question=question,
                context=context,
                results=results,
                include_citations=include_citations
            )
        else:
            answer = self._generate_answer(
                question=question,
                context=context
            )

            # Step 5: Assemble response
            response = {
                'answer': answer,
                'question': question,
                'metadata': {
                    'chunks_retrieved': len(results),
                    'query_intent': processed_query['query_metadata']['intent'],
                    'filters_applied': processed_query['filters']
                }
            }

            # Add citations if requested
            if include_citations:
                response['citations'] = self.retrieval_service.generate_citations(results)

            return response

    def _generate_answer(self, question: str, context: str) -> str:
        """
        Generate answer using Claude with retrieved context.

        Args:
            question: User's question
            context: Retrieved context

        Returns:
            Generated answer
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(question, context)

        answer = invoke_model(
            client=self.bedrock_client,
            model_id=self.generation_model_id,
            prompt=user_prompt,
            max_tokens=2000,
            system_prompt=system_prompt
        )

        return answer

    def _generate_streaming_answer(
        self,
        question: str,
        context: str,
        results: List[RetrievalResult],
        include_citations: bool
    ) -> Dict[str, Any]:
        """
        Generate streaming answer with metadata.

        Args:
            question: User's question
            context: Retrieved context
            results: Retrieval results
            include_citations: Whether to include citations

        Returns:
            Dict with stream generator and metadata
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(question, context)

        # Create messages for streaming API
        messages = [
            {
                "role": "user",
                "content": [{"text": user_prompt}]
            }
        ]

        # Get streaming response
        stream = invoke_model_streaming(
            client=self.bedrock_client,
            model_id=self.generation_model_id,
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=2000
        )

        response = {
            'stream': stream,
            'question': question,
            'metadata': {
                'chunks_retrieved': len(results)
            }
        }

        if include_citations:
            response['citations'] = self.retrieval_service.generate_citations(results)

        return response

    def _build_system_prompt(self) -> str:
        """
        Build system prompt for answer generation.

        Returns:
            System prompt string
        """
        return """You are a helpful AI assistant that answers questions based on provided context.

Your responsibilities:
1. Answer questions accurately using ONLY the information in the provided context
2. If the context doesn't contain enough information, say so clearly
3. Cite sources when making specific claims
4. Be concise but thorough
5. Format your answers clearly with proper structure

Guidelines:
- Do NOT make up information not in the context
- Do NOT use external knowledge beyond the context
- If asked about something not in the context, explain what information is available
- Use bullet points or numbered lists for clarity when appropriate
- Keep answers focused and relevant to the question"""

    def _build_user_prompt(self, question: str, context: str) -> str:
        """
        Build user prompt with question and context.

        Args:
            question: User's question
            context: Retrieved context

        Returns:
            Formatted user prompt
        """
        return f"""Context from knowledge base:

{context}

---

Question: {question}

Please provide a comprehensive answer based on the context above. If the context doesn't contain sufficient information to answer the question, explain what information is available and what is missing."""

    def multi_query(
        self,
        questions: List[str],
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Process multiple questions in batch.

        Args:
            questions: List of questions
            filters: Optional metadata filters
            top_k: Number of chunks per query

        Returns:
            List of answers with metadata
        """
        results = []

        for question in questions:
            try:
                answer = self.query(
                    question=question,
                    filters=filters,
                    top_k=top_k,
                    include_citations=True,
                    stream=False
                )
                results.append(answer)
            except Exception as e:
                results.append({
                    'question': question,
                    'error': str(e),
                    'answer': None
                })

        return results

    def conversational_query(
        self,
        question: str,
        conversation_history: List[Dict[str, str]],
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Process query with conversation context.

        Args:
            question: Current question
            conversation_history: Previous messages [{"role": "user"|"assistant", "content": "..."}]
            filters: Optional metadata filters
            top_k: Number of chunks to retrieve

        Returns:
            Answer with metadata
        """
        # Combine recent conversation for context
        conversation_context = self._format_conversation(conversation_history[-6:])  # Last 3 turns

        # Enhance question with conversation context
        enhanced_question = f"{conversation_context}\n\nCurrent question: {question}"

        # Process as regular query
        return self.query(
            question=enhanced_question,
            filters=filters,
            top_k=top_k,
            include_citations=True,
            stream=False
        )

    def _format_conversation(self, history: List[Dict[str, str]]) -> str:
        """
        Format conversation history for context.

        Args:
            history: Conversation messages

        Returns:
            Formatted conversation string
        """
        if not history:
            return ""

        formatted = "Previous conversation:\n"
        for msg in history:
            role = msg.get('role', 'user').title()
            content = msg.get('content', '')
            formatted += f"{role}: {content}\n"

        return formatted

    def search_documents(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant documents without generating an answer.

        Args:
            query: Search query
            filters: Optional metadata filters
            top_k: Number of results

        Returns:
            List of matching chunks with metadata
        """
        # Process query
        processed_query = self.query_processor.process_query(
            query=query,
            filters=filters,
            top_k=top_k
        )

        # Retrieve chunks
        results = self.retrieval_service.retrieve(
            query_embedding=processed_query['embedding'],
            top_k=top_k,
            filters=processed_query['filters']
        )

        # Convert to dict format
        return [result.to_dict() for result in results]
