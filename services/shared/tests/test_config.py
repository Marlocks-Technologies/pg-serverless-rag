"""Tests for configuration loading."""

import os
import pytest
from shared.config import load_config, AppConfig


def test_load_config_with_all_variables(monkeypatch):
    """Test that load_config succeeds when all required variables are set."""
    env_vars = {
        "AWS_REGION": "us-east-1",
        "INGESTION_BUCKET": "test-ingestion",
        "STAGING_BUCKET": "test-staging",
        "VECTORS_BUCKET": "test-vectors",
        "CHAT_HISTORY_TABLE": "test-table",
        "KNOWLEDGE_BASE_ID": "test-kb-id",
        "EMBEDDING_MODEL_ID": "amazon.titan-embed-text-v2:0",
        "GENERATION_MODEL_ID": "anthropic.claude-3-sonnet-20240229-v1:0",
        "HAIKU_MODEL_ID": "anthropic.claude-3-haiku-20240307-v1:0",
        "LOG_LEVEL": "DEBUG",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    config = load_config()

    assert isinstance(config, AppConfig)
    assert config.aws_region == "us-east-1"
    assert config.ingestion_bucket == "test-ingestion"
    assert config.staging_bucket == "test-staging"
    assert config.vectors_bucket == "test-vectors"
    assert config.chat_history_table == "test-table"
    assert config.knowledge_base_id == "test-kb-id"
    assert config.log_level == "DEBUG"


def test_load_config_missing_required_variable(monkeypatch):
    """Test that load_config raises EnvironmentError when required variable is missing."""
    # Set all but one variable
    env_vars = {
        "AWS_REGION": "us-east-1",
        "INGESTION_BUCKET": "test-ingestion",
        "STAGING_BUCKET": "test-staging",
        "VECTORS_BUCKET": "test-vectors",
        "CHAT_HISTORY_TABLE": "test-table",
        # Missing KNOWLEDGE_BASE_ID
        "EMBEDDING_MODEL_ID": "amazon.titan-embed-text-v2:0",
        "GENERATION_MODEL_ID": "anthropic.claude-3-sonnet-20240229-v1:0",
        "HAIKU_MODEL_ID": "anthropic.claude-3-haiku-20240307-v1:0",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    # Ensure KNOWLEDGE_BASE_ID is not set
    monkeypatch.delenv("KNOWLEDGE_BASE_ID", raising=False)

    with pytest.raises(EnvironmentError) as exc_info:
        load_config()

    assert "Missing required env vars" in str(exc_info.value)
    assert "KNOWLEDGE_BASE_ID" in str(exc_info.value)


def test_load_config_default_log_level(monkeypatch):
    """Test that LOG_LEVEL defaults to INFO when not set."""
    env_vars = {
        "AWS_REGION": "us-east-1",
        "INGESTION_BUCKET": "test-ingestion",
        "STAGING_BUCKET": "test-staging",
        "VECTORS_BUCKET": "test-vectors",
        "CHAT_HISTORY_TABLE": "test-table",
        "KNOWLEDGE_BASE_ID": "test-kb-id",
        "EMBEDDING_MODEL_ID": "amazon.titan-embed-text-v2:0",
        "GENERATION_MODEL_ID": "anthropic.claude-3-sonnet-20240229-v1:0",
        "HAIKU_MODEL_ID": "anthropic.claude-3-haiku-20240307-v1:0",
        # LOG_LEVEL not set
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    monkeypatch.delenv("LOG_LEVEL", raising=False)

    config = load_config()

    assert config.log_level == "INFO"


def test_load_config_multiple_missing_variables(monkeypatch):
    """Test error message includes all missing variables."""
    # Only set a few variables
    env_vars = {
        "AWS_REGION": "us-east-1",
        "INGESTION_BUCKET": "test-ingestion",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    # Clear all other required variables
    for key in [
        "STAGING_BUCKET",
        "VECTORS_BUCKET",
        "CHAT_HISTORY_TABLE",
        "KNOWLEDGE_BASE_ID",
        "EMBEDDING_MODEL_ID",
        "GENERATION_MODEL_ID",
        "HAIKU_MODEL_ID",
    ]:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(EnvironmentError) as exc_info:
        load_config()

    error_message = str(exc_info.value)
    assert "STAGING_BUCKET" in error_message
    assert "KNOWLEDGE_BASE_ID" in error_message
