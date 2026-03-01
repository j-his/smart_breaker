"""Tests for LLM chat module."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from backend.llm.chat import get_client, chat_completion, chat_stream, _mock_response


class TestLLMChat:
    """Tests for chat module with mocked AsyncOpenAI."""

    def test_get_client_returns_async_openai(self):
        """get_client should return an AsyncOpenAI instance."""
        import backend.llm.chat as chat_module
        chat_module._client = None  # reset singleton
        client = get_client()
        from openai import AsyncOpenAI
        assert isinstance(client, AsyncOpenAI)
        chat_module._client = None  # cleanup

    @pytest.mark.asyncio
    async def test_chat_completion_mock_when_disabled(self):
        """With ENABLE_LLM=False, should return mock without API call."""
        with patch("backend.llm.chat.config") as mock_config:
            mock_config.ENABLE_LLM = False
            result = await chat_completion("How can I save money?")
            assert isinstance(result, str)
            assert len(result) > 0
            # Mock should mention savings since the question is about money
            assert "save" in result.lower() or "cost" in result.lower() or "energy" in result.lower()

    @pytest.mark.asyncio
    async def test_chat_stream_yields_chunks(self):
        """chat_stream should yield string chunks from a mocked streaming response."""
        # Build a mock streaming response
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta = MagicMock()
        chunk1.choices[0].delta.content = "Hello "

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta = MagicMock()
        chunk2.choices[0].delta.content = "world!"

        async def mock_stream():
            yield chunk1
            yield chunk2

        mock_client = AsyncMock()
        mock_response = mock_stream()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("backend.llm.chat.config") as mock_config, \
             patch("backend.llm.chat.get_client", return_value=mock_client):
            mock_config.ENABLE_LLM = True
            mock_config.LLM_CHAT_MODEL = "test-model"

            chunks = []
            async for chunk in chat_stream("test", model="test-model"):
                chunks.append(chunk)

            assert chunks == ["Hello ", "world!"]

    @pytest.mark.asyncio
    async def test_chat_completion_falls_back_on_exception(self):
        """On API exception, should return mock response instead of raising."""
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API down")
        )

        with patch("backend.llm.chat.config") as mock_config, \
             patch("backend.llm.chat.get_client", return_value=mock_client):
            mock_config.ENABLE_LLM = True
            mock_config.LLM_CHAT_MODEL = "test-model"

            result = await chat_completion("Tell me about my schedule")
            assert isinstance(result, str)
            assert len(result) > 0
