"""Configuration loader using environment variables with validation."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class AppConfig:
    aws_region: str
    ingestion_bucket: str
    staging_bucket: str
    vectors_bucket: str
    chat_history_table: str
    knowledge_base_id: str
    embedding_model_id: str
    generation_model_id: str
    haiku_model_id: str
    log_level: str = "INFO"


def load_config() -> AppConfig:
    """Load and validate configuration from environment variables.

    Returns:
        AppConfig: Populated configuration dataclass.

    Raises:
        EnvironmentError: If any required environment variables are missing.
    """
    required = [
        "AWS_REGION",
        "INGESTION_BUCKET",
        "STAGING_BUCKET",
        "VECTORS_BUCKET",
        "CHAT_HISTORY_TABLE",
        "KNOWLEDGE_BASE_ID",
        "EMBEDDING_MODEL_ID",
        "GENERATION_MODEL_ID",
        "HAIKU_MODEL_ID",
    ]

    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {missing}")

    return AppConfig(
        aws_region=os.environ["AWS_REGION"],
        ingestion_bucket=os.environ["INGESTION_BUCKET"],
        staging_bucket=os.environ["STAGING_BUCKET"],
        vectors_bucket=os.environ["VECTORS_BUCKET"],
        chat_history_table=os.environ["CHAT_HISTORY_TABLE"],
        knowledge_base_id=os.environ["KNOWLEDGE_BASE_ID"],
        embedding_model_id=os.environ["EMBEDDING_MODEL_ID"],
        generation_model_id=os.environ["GENERATION_MODEL_ID"],
        haiku_model_id=os.environ["HAIKU_MODEL_ID"],
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
