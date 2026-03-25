"""Bedrock client wrappers for the RAG Platform.

Provides thin, testable wrappers around the AWS Bedrock runtime and agent APIs.
All functions accept an explicit boto3 client for dependency injection in tests.
"""

import json
from typing import Any, Generator, Iterator, Optional


def invoke_model(
    client: Any,
    model_id: str,
    prompt: str,
    max_tokens: int = 1000,
    system_prompt: Optional[str] = None,
) -> str:
    """Invoke a Bedrock model using the Converse API and return the text response.

    Args:
        client: boto3 bedrock-runtime client.
        model_id: Bedrock model ID (e.g. "anthropic.claude-3-haiku-20240307-v1:0").
        prompt: User message text.
        max_tokens: Maximum tokens to generate in the response.
        system_prompt: Optional system prompt string.

    Returns:
        The model's text response as a plain string.

    Raises:
        RuntimeError: If the model returns an unexpected response structure.
    """
    messages = [{"role": "user", "content": [{"text": prompt}]}]
    kwargs: dict = {
        "modelId": model_id,
        "messages": messages,
        "inferenceConfig": {"maxTokens": max_tokens},
    }
    if system_prompt:
        kwargs["system"] = [{"text": system_prompt}]

    response = client.converse(**kwargs)

    try:
        return response["output"]["message"]["content"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(
            f"Unexpected Bedrock Converse response structure: {response}"
        ) from exc


def invoke_model_streaming(
    client: Any,
    model_id: str,
    messages: list[dict],
    system_prompt: str = "",
    max_tokens: int = 2000,
) -> Iterator[str]:
    """Invoke a Bedrock model with streaming and yield text chunks.

    Args:
        client: boto3 bedrock-runtime client.
        model_id: Bedrock model ID.
        messages: List of Converse-API message dicts with "role" and "content".
        system_prompt: System prompt text.
        max_tokens: Maximum tokens to generate.

    Yields:
        Text chunks from the streaming response as they arrive.
    """
    kwargs: dict = {
        "modelId": model_id,
        "messages": messages,
        "inferenceConfig": {"maxTokens": max_tokens},
    }
    if system_prompt:
        kwargs["system"] = [{"text": system_prompt}]

    response = client.converse_stream(**kwargs)
    stream = response.get("stream")
    if stream is None:
        return

    for event in stream:
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            text = delta.get("text", "")
            if text:
                yield text
        elif "messageStop" in event:
            break


def retrieve_and_generate(
    client: Any,
    knowledge_base_id: str,
    query: str,
    session_id: Optional[str] = None,
    top_k: int = 5,
    filters: Optional[dict] = None,
) -> dict:
    """Use Bedrock RetrieveAndGenerate to answer a query from a Knowledge Base.

    Args:
        client: boto3 bedrock-agent-runtime client.
        knowledge_base_id: Bedrock Knowledge Base ID.
        query: Natural language query to answer.
        session_id: Optional session ID for multi-turn conversation continuity.
        top_k: Number of chunks to retrieve from the knowledge base.
        filters: Optional metadata filter dict (passed as retrievalFilter).

    Returns:
        Dict containing:
          - "output": {"text": "<generated answer>"}
          - "citations": list of citation objects
          - "sessionId": session ID string
    """
    retrieval_config: dict = {
        "vectorSearchConfiguration": {"numberOfResults": top_k}
    }
    if filters:
        retrieval_config["vectorSearchConfiguration"]["filter"] = filters

    kwargs: dict = {
        "input": {"text": query},
        "retrieveAndGenerateConfiguration": {
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": knowledge_base_id,
                "modelArn": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
                "retrievalConfiguration": retrieval_config,
            },
        },
    }

    if session_id:
        kwargs["sessionId"] = session_id

    response = client.retrieve_and_generate(**kwargs)

    return {
        "output": response.get("output", {}),
        "citations": response.get("citations", []),
        "sessionId": response.get("sessionId", ""),
    }


def retrieve(
    client: Any,
    knowledge_base_id: str,
    query: str,
    top_k: int = 5,
    filters: Optional[dict] = None,
) -> list[dict]:
    """Retrieve relevant document chunks from a Bedrock Knowledge Base.

    Args:
        client: boto3 bedrock-agent-runtime client.
        knowledge_base_id: Bedrock Knowledge Base ID.
        query: Natural language query.
        top_k: Number of chunks to return.
        filters: Optional metadata filter dict.

    Returns:
        List of retrieval result dicts, each containing:
          - "content": {"text": "<chunk text>"}
          - "location": source location dict
          - "score": relevance score float
          - "metadata": additional metadata dict
    """
    retrieval_config: dict = {
        "vectorSearchConfiguration": {"numberOfResults": top_k}
    }
    if filters:
        retrieval_config["vectorSearchConfiguration"]["filter"] = filters

    response = client.retrieve(
        knowledgeBaseId=knowledge_base_id,
        retrievalQuery={"text": query},
        retrievalConfiguration=retrieval_config,
    )

    results = []
    for item in response.get("retrievalResults", []):
        results.append(
            {
                "content": item.get("content", {}),
                "location": item.get("location", {}),
                "score": item.get("score", 0.0),
                "metadata": item.get("metadata", {}),
            }
        )

    return results


def generate_embeddings(
    text: str,
    model_id: str = "amazon.titan-embed-text-v2:0",
    client: Any = None
) -> list[float]:
    """
    Generate embeddings using Amazon Bedrock Titan Embeddings.

    Args:
        text: Text to embed
        model_id: Embedding model ID (default: Titan Embeddings v2)
        client: Optional boto3 bedrock-runtime client (created if not provided)

    Returns:
        List of floats representing the embedding vector (1536-dim for Titan v2)

    Example:
        >>> import boto3
        >>> bedrock = boto3.client('bedrock-runtime')
        >>> embedding = generate_embeddings("Hello world", client=bedrock)
        >>> len(embedding)
        1536
    """
    print(f"[DEBUG] generate_embeddings called with text length: {len(text)}, model: {model_id}")

    if client is None:
        print("[DEBUG] Creating new bedrock-runtime client")
        import boto3
        client = boto3.client('bedrock-runtime')
        print("[DEBUG] Client created")
    else:
        print("[DEBUG] Using provided client")

    # Titan Embeddings v2 request format
    print("[DEBUG] Creating request body")
    body = json.dumps({
        "inputText": text[:500]  # Truncate for logging safety
    })
    print(f"[DEBUG] Request body created, size: {len(body)} bytes")

    print(f"[DEBUG] Calling invoke_model with modelId: {model_id}")
    try:
        response = client.invoke_model(
            modelId=model_id,
            body=body,
            contentType='application/json',
            accept='application/json'
        )
        print("[DEBUG] invoke_model returned successfully")
    except Exception as e:
        print(f"[ERROR] invoke_model failed: {type(e).__name__}: {str(e)}")
        raise

    print("[DEBUG] Reading response body")
    response_body = json.loads(response['body'].read())
    print(f"[DEBUG] Response parsed, keys: {list(response_body.keys())}")

    embedding = response_body['embedding']
    print(f"[DEBUG] Embedding extracted, dimension: {len(embedding)}")

    return embedding
