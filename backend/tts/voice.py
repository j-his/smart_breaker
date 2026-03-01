"""ElevenLabs TTS — streaming text-to-speech with WebSocket broadcast."""
from __future__ import annotations

import base64
import logging
from typing import AsyncGenerator

from backend import config
from backend.api.websocket import ws_manager, make_envelope

logger = logging.getLogger(__name__)

_tts_client = None


def get_tts_client():
    """Return a singleton AsyncElevenLabs client."""
    global _tts_client
    if _tts_client is None:
        from elevenlabs import AsyncElevenLabs
        _tts_client = AsyncElevenLabs(api_key=config.ELEVENLABS_API_KEY)
    return _tts_client


async def text_to_speech_stream(
    text: str,
    insight_id: str,
) -> AsyncGenerator[str, None]:
    """Convert text to speech and yield base64-encoded MP3 chunks.

    Uses ElevenLabs convert() which returns AsyncIterator[bytes].
    Each chunk is base64-encoded for safe WebSocket text transport.
    """
    client = get_tts_client()
    audio_stream = await client.text_to_speech.convert(
        voice_id=config.ELEVENLABS_VOICE_ID,
        text=text,
        model_id=config.ELEVENLABS_MODEL_ID,
        output_format=config.ELEVENLABS_OUTPUT_FORMAT,
    )

    async for chunk in audio_stream:
        if chunk:
            yield base64.b64encode(chunk).decode("ascii")


async def speak_insight(text: str, insight_id: str) -> None:
    """Convert insight text to speech and broadcast via WebSocket.

    Guards: skips if TTS is disabled or no API key configured.
    Sends chunks with is_final=False, then a final marker with is_final=True.
    """
    if not config.ELEVENLABS_TTS_ENABLED:
        logger.debug("TTS disabled, skipping speak_insight")
        return

    if not config.ELEVENLABS_API_KEY:
        logger.debug("No ElevenLabs API key, skipping speak_insight")
        return

    try:
        async for b64_chunk in text_to_speech_stream(text, insight_id):
            await ws_manager.broadcast(make_envelope("tts_audio", {
                "audio": b64_chunk,
                "format": "mp3",
                "insight_id": insight_id,
                "is_final": False,
            }))

        # Send final marker
        await ws_manager.broadcast(make_envelope("tts_audio", {
            "audio": "",
            "format": "mp3",
            "insight_id": insight_id,
            "is_final": True,
        }))
        logger.info("TTS complete for insight %s", insight_id)

    except Exception as e:
        logger.error("TTS speak_insight failed: %s", e)
