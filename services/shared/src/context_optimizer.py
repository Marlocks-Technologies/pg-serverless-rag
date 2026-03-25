"""
Context Optimizer - Optimizes conversation context for token efficiency.

Phase 5: Compresses old conversation turns to reduce token usage while maintaining context.
"""

from typing import List, Dict, Any
from shared.bedrock_wrappers import invoke_model
import boto3


class ContextOptimizer:
    """Optimizes conversation context to reduce token usage."""

    def __init__(
        self,
        model_id: str = "anthropic.claude-3-haiku-20240307-v1:0",
        region: str = "us-east-1"
    ):
        """
        Initialize context optimizer.

        Args:
            model_id: Model ID for summarization
            region: AWS region
        """
        self.model_id = model_id
        self.region = region
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=region)

    def optimize_conversation_context(
        self,
        conversation_history: List[Dict[str, str]],
        max_tokens: int = 2000,
        preserve_recent_turns: int = 3
    ) -> List[Dict[str, str]]:
        """
        Optimize conversation history to fit within token budget.

        Args:
            conversation_history: Full conversation history
            max_tokens: Maximum tokens for context
            preserve_recent_turns: Number of recent turns to preserve verbatim

        Returns:
            Optimized conversation history
        """
        if not conversation_history:
            return []

        # Calculate approximate token count (4 chars ≈ 1 token)
        total_chars = sum(len(msg['content']) for msg in conversation_history)
        estimated_tokens = total_chars // 4

        # If within budget, return as-is
        if estimated_tokens <= max_tokens:
            return conversation_history

        # Split into old and recent
        if len(conversation_history) <= preserve_recent_turns * 2:
            # Too few messages, just truncate if needed
            return self._truncate_messages(conversation_history, max_tokens)

        recent_messages = conversation_history[-(preserve_recent_turns * 2):]
        old_messages = conversation_history[:-(preserve_recent_turns * 2)]

        # Summarize old messages
        summary = self._summarize_conversation(old_messages)

        # Combine summary with recent messages
        optimized = [
            {
                'role': 'assistant',
                'content': f"[Previous conversation summary: {summary}]"
            }
        ] + recent_messages

        # Verify token budget
        optimized_chars = sum(len(msg['content']) for msg in optimized)
        if optimized_chars // 4 > max_tokens:
            # Still too large, truncate further
            return self._truncate_messages(optimized, max_tokens)

        return optimized

    def _summarize_conversation(self, messages: List[Dict[str, str]]) -> str:
        """
        Summarize a list of conversation messages.

        Args:
            messages: Messages to summarize

        Returns:
            Summary text
        """
        if not messages:
            return ""

        # Format conversation for summarization
        conversation_text = self._format_messages(messages)

        # Build summarization prompt
        prompt = f"""Summarize the following conversation in 2-3 sentences, preserving key points and context:

{conversation_text}

Summary:"""

        try:
            summary = invoke_model(
                client=self.bedrock_client,
                model_id=self.model_id,
                prompt=prompt,
                max_tokens=150,
                system_prompt="You are a helpful assistant that creates concise conversation summaries."
            )

            return summary.strip()

        except Exception as e:
            # Fallback: create simple summary
            return self._create_simple_summary(messages)

    def _create_simple_summary(self, messages: List[Dict[str, str]]) -> str:
        """Create simple summary without LLM."""
        topics = []

        for msg in messages:
            if msg['role'] == 'user':
                # Extract first question-like sentence
                content = msg['content']
                if '?' in content:
                    question = content.split('?')[0] + '?'
                    if len(question) < 100:
                        topics.append(question)

        if topics:
            return f"User asked about: {', '.join(topics[:3])}"
        else:
            return "Previous conversation context"

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Format messages for display."""
        formatted = []

        for msg in messages:
            role = msg['role'].title()
            content = msg['content']
            formatted.append(f"{role}: {content}")

        return "\n\n".join(formatted)

    def _truncate_messages(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int
    ) -> List[Dict[str, str]]:
        """
        Truncate messages to fit token budget.

        Args:
            messages: Messages to truncate
            max_tokens: Maximum tokens

        Returns:
            Truncated messages
        """
        max_chars = max_tokens * 4  # Rough approximation
        truncated = []
        total_chars = 0

        # Take most recent messages that fit
        for msg in reversed(messages):
            msg_chars = len(msg['content'])

            if total_chars + msg_chars > max_chars:
                break

            truncated.insert(0, msg)
            total_chars += msg_chars

        return truncated if truncated else messages[-1:]

    def compress_context_window(
        self,
        context: str,
        max_tokens: int = 4000
    ) -> str:
        """
        Compress a context window to fit token budget.

        Args:
            context: Context text
            max_tokens: Maximum tokens

        Returns:
            Compressed context
        """
        # Check if compression needed
        estimated_tokens = len(context) // 4

        if estimated_tokens <= max_tokens:
            return context

        # Split into chunks
        chunks = context.split('\n---\n')

        if len(chunks) <= 1:
            # Single chunk, just truncate
            max_chars = max_tokens * 4
            return context[:max_chars] + "\n[...truncated]"

        # Keep most relevant chunks (assume they're ranked by relevance)
        compressed_chunks = []
        total_chars = 0
        max_chars = max_tokens * 4

        for chunk in chunks:
            if total_chars + len(chunk) > max_chars:
                break

            compressed_chunks.append(chunk)
            total_chars += len(chunk)

        if compressed_chunks:
            return '\n---\n'.join(compressed_chunks)
        else:
            # Return at least the first chunk (truncated)
            return chunks[0][:max_chars] + "\n[...truncated]"

    def adaptive_context_length(
        self,
        query_complexity: str,
        default_max: int = 4000
    ) -> int:
        """
        Determine optimal context length based on query complexity.

        Args:
            query_complexity: 'simple', 'moderate', or 'complex'
            default_max: Default maximum tokens

        Returns:
            Recommended max tokens
        """
        complexity_map = {
            'simple': int(default_max * 0.5),      # 2000 tokens
            'moderate': default_max,                 # 4000 tokens
            'complex': int(default_max * 1.5)      # 6000 tokens
        }

        return complexity_map.get(query_complexity, default_max)

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        # Rough approximation: 4 chars = 1 token
        # More accurate would use tiktoken, but this is good enough
        return len(text) // 4

    def should_compress(
        self,
        conversation_history: List[Dict[str, str]],
        threshold_tokens: int = 2000
    ) -> bool:
        """
        Determine if conversation history should be compressed.

        Args:
            conversation_history: Conversation messages
            threshold_tokens: Token threshold for compression

        Returns:
            True if should compress
        """
        total_chars = sum(len(msg['content']) for msg in conversation_history)
        estimated_tokens = total_chars // 4

        return estimated_tokens > threshold_tokens
