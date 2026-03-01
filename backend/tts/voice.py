"""ElevenLabs TTS — streaming text-to-speech with WebSocket broadcast.

Includes a priority queue so only one TTS stream runs at a time.
Chat responses (priority=0) take precedence over narrator insights (priority=1).
All text is stripped of markdown before being sent to ElevenLabs.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import re
from typing import AsyncGenerator

from backend import config
from backend.api.websocket import ws_manager, make_envelope

logger = logging.getLogger(__name__)

_tts_client = None
_tts_lock = asyncio.Lock()


# ── Markdown Stripping ───────────────────────────────────────────────────────

def strip_markdown(text: str) -> str:
    """Remove markdown formatting so TTS reads clean prose."""
    # Remove code blocks (``` ... ```)
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove inline code (`...`)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove images ![alt](url)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    # Convert links [text](url) to just text
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Remove bold **text** or __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    # Remove italic *text* or _text_
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", text)
    # Remove headers (# ... )
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Remove bullet points (- or * at start of line)
    text = re.sub(r"^[\-\*]\s+", "", text, flags=re.MULTILINE)
    # Remove numbered list prefixes
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
    # Remove blockquotes
    text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
    # Collapse multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Client ───────────────────────────────────────────────────────────────────

def get_tts_client():
    """Return a singleton AsyncElevenLabs client."""
    global _tts_client
    if _tts_client is None:
        from elevenlabs import AsyncElevenLabs
        _tts_client = AsyncElevenLabs(api_key=config.ELEVENLABS_API_KEY)
    return _tts_client


def _get_active_voice_id() -> str:
    """Get the currently selected voice ID from app state, falling back to config."""
    try:
        from backend.api.routes import _state
        return _state.get("voice_id", config.ELEVENLABS_VOICE_ID)
    except ImportError:
        return config.ELEVENLABS_VOICE_ID


# ── Core Stream ──────────────────────────────────────────────────────────────

async def text_to_speech_stream(
    text: str,
    insight_id: str,
) -> AsyncGenerator[str, None]:
    """Convert text to speech and yield base64-encoded MP3 chunks.

    Uses ElevenLabs convert() which returns AsyncIterator[bytes].
    Each chunk is base64-encoded for safe WebSocket text transport.
    """
    client = get_tts_client()
    clean_text = strip_markdown(text)
    if not clean_text:
        return

    audio_stream = client.text_to_speech.convert(
        voice_id=_get_active_voice_id(),
        text=clean_text,
        model_id=config.ELEVENLABS_MODEL_ID,
        output_format=config.ELEVENLABS_OUTPUT_FORMAT,
    )

    async for chunk in audio_stream:
        if chunk:
            yield base64.b64encode(chunk).decode("ascii")


# ── Public API ───────────────────────────────────────────────────────────────

async def speak_to_client(text: str, websocket, message_id: str) -> None:
    """Convert text to speech and send audio to a specific WebSocket client.

    Used for chat responses — only the person who asked hears the answer.
    Has high priority: acquires the TTS lock to prevent overlap with narrator.
    """
    if not config.ELEVENLABS_TTS_ENABLED or not config.ELEVENLABS_API_KEY:
        return

    async with _tts_lock:
        logger.info("TTS lock acquired for chat response %s", message_id)
        try:
            async for b64_chunk in text_to_speech_stream(text, message_id):
                await ws_manager.send_to(websocket, make_envelope("tts_audio", {
                    "audio": b64_chunk,
                    "format": "mp3",
                    "insight_id": message_id,
                    "is_final": False,
                }))
        except Exception as e:
            logger.error("TTS speak_to_client failed: %s", e)
        finally:
            await ws_manager.send_to(websocket, make_envelope("tts_audio", {
                "audio": "",
                "format": "mp3",
                "insight_id": message_id,
                "is_final": True,
            }))


async def speak_insight(text: str, insight_id: str) -> None:
    """Convert insight text to speech and broadcast via WebSocket.

    Lower priority than chat — if the lock is already held (chat is speaking),
    this insight is dropped to avoid queueing up stale narrations.
    """
    if not config.ELEVENLABS_TTS_ENABLED:
        logger.debug("TTS disabled, skipping speak_insight")
        return

    if not config.ELEVENLABS_API_KEY:
        logger.debug("No ElevenLabs API key, skipping speak_insight")
        return

    if _tts_lock.locked():
        logger.info("TTS busy (chat has priority), dropping insight %s", insight_id)
        # Still send the final marker so the client doesn't hang waiting
        await ws_manager.broadcast(make_envelope("tts_audio", {
            "audio": "",
            "format": "mp3",
            "insight_id": insight_id,
            "is_final": True,
        }))
        return

    async with _tts_lock:
        logger.info("TTS lock acquired for insight %s", insight_id)
        try:
            async for b64_chunk in text_to_speech_stream(text, insight_id):
                await ws_manager.broadcast(make_envelope("tts_audio", {
                    "audio": b64_chunk,
                    "format": "mp3",
                    "insight_id": insight_id,
                    "is_final": False,
                }))
            logger.info("TTS complete for insight %s", insight_id)
        except Exception as e:
            logger.error("TTS speak_insight failed: %s", e)
        finally:
            await ws_manager.broadcast(make_envelope("tts_audio", {
                "audio": "",
                "format": "mp3",
                "insight_id": insight_id,
                "is_final": True,
            }))
