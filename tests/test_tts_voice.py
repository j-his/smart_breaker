"""Tests for ElevenLabs TTS voice module."""
import base64

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from backend.tts.voice import speak_insight, text_to_speech_stream


class TestTTSVoice:
    """Tests for TTS voice module."""

    @pytest.mark.asyncio
    async def test_speak_insight_skips_when_disabled(self):
        """When TTS is disabled, speak_insight should return without action."""
        with patch("backend.tts.voice.config") as mock_config, \
             patch("backend.tts.voice.ws_manager") as mock_ws:
            mock_config.ELEVENLABS_TTS_ENABLED = False
            mock_ws.broadcast = AsyncMock()

            await speak_insight("test text", "ins-001")

            mock_ws.broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_speak_insight_skips_when_no_api_key(self):
        """When no API key, speak_insight should return without action."""
        with patch("backend.tts.voice.config") as mock_config, \
             patch("backend.tts.voice.ws_manager") as mock_ws:
            mock_config.ELEVENLABS_TTS_ENABLED = True
            mock_config.ELEVENLABS_API_KEY = ""
            mock_ws.broadcast = AsyncMock()

            await speak_insight("test text", "ins-002")

            mock_ws.broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_text_to_speech_stream_yields_base64(self):
        """Stream should yield base64-encoded strings from raw audio bytes."""
        raw_bytes = [b"audio_chunk_1", b"audio_chunk_2"]

        async def mock_audio_iter():
            for chunk in raw_bytes:
                yield chunk

        mock_client = MagicMock()
        mock_client.text_to_speech.convert = AsyncMock(return_value=mock_audio_iter())

        with patch("backend.tts.voice.get_tts_client", return_value=mock_client), \
             patch("backend.tts.voice.config") as mock_config:
            mock_config.ELEVENLABS_VOICE_ID = "test-voice"
            mock_config.ELEVENLABS_MODEL_ID = "test-model"
            mock_config.ELEVENLABS_OUTPUT_FORMAT = "mp3_44100_128"

            chunks = []
            async for b64 in text_to_speech_stream("hello", "ins-003"):
                chunks.append(b64)

            assert len(chunks) == 2
            # Verify they're valid base64 that decode to original bytes
            assert base64.b64decode(chunks[0]) == b"audio_chunk_1"
            assert base64.b64decode(chunks[1]) == b"audio_chunk_2"

    @pytest.mark.asyncio
    async def test_speak_insight_broadcasts_chunks_and_final(self):
        """speak_insight should broadcast audio chunks then a final marker."""
        async def mock_tts_stream(text, insight_id):
            yield "QUFB"  # base64 of b"AAA"
            yield "QkJC"  # base64 of b"BBB"

        with patch("backend.tts.voice.config") as mock_config, \
             patch("backend.tts.voice.ws_manager") as mock_ws, \
             patch("backend.tts.voice.text_to_speech_stream", side_effect=mock_tts_stream):
            mock_config.ELEVENLABS_TTS_ENABLED = True
            mock_config.ELEVENLABS_API_KEY = "sk_test"
            mock_ws.broadcast = AsyncMock()

            await speak_insight("test insight", "ins-004")

            # 2 audio chunks + 1 final marker = 3 broadcasts
            assert mock_ws.broadcast.call_count == 3

            # Check final message has is_final=True and empty audio
            final_call = mock_ws.broadcast.call_args_list[-1][0][0]
            assert final_call["data"]["is_final"] is True
            assert final_call["data"]["audio"] == ""
            assert final_call["data"]["insight_id"] == "ins-004"
