"""Tests for LLM narrator event handlers."""
import pytest
from unittest.mock import patch, AsyncMock

from backend.events import Event
from backend.llm.narrator import (
    on_schedule_updated,
    on_anomaly_detected,
    _generate_insight,
)


class TestNarrator:
    """Tests for narrator event handlers."""

    @pytest.mark.asyncio
    async def test_on_schedule_updated_broadcasts_insight(self):
        """When tasks are moved, should broadcast an insight."""
        event = Event(
            type="schedule_updated",
            data={
                "optimized_events": [
                    {"title": "Run Dryer", "optimized_start_hour": 2, "original_start_hour": 18},
                ],
                "total_savings_cents": 15.0,
                "total_carbon_avoided_g": 200,
            },
        )

        with patch("backend.llm.narrator.chat_completion", new_callable=AsyncMock) as mock_llm, \
             patch("backend.llm.narrator.ws_manager") as mock_ws, \
             patch("backend.llm.narrator.config") as mock_config:
            mock_llm.return_value = "Great news! Your dryer was moved to save 15 cents."
            mock_ws.broadcast = AsyncMock()
            mock_config.ELEVENLABS_TTS_ENABLED = False
            mock_config.ELEVENLABS_API_KEY = ""
            mock_config.LLM_NARRATOR_MODEL = "test"

            await on_schedule_updated(event)

            mock_ws.broadcast.assert_called_once()
            call_args = mock_ws.broadcast.call_args[0][0]
            assert call_args["type"] == "insight"
            assert call_args["data"]["category"] == "schedule_optimization"

    @pytest.mark.asyncio
    async def test_on_schedule_updated_skips_when_nothing_moved(self):
        """If no tasks were actually moved, no insight should be generated."""
        event = Event(
            type="schedule_updated",
            data={
                "optimized_events": [
                    {"title": "Cook", "optimized_start_hour": 19, "original_start_hour": 19},
                ],
            },
        )

        with patch("backend.llm.narrator.chat_completion", new_callable=AsyncMock) as mock_llm, \
             patch("backend.llm.narrator.ws_manager") as mock_ws:
            mock_ws.broadcast = AsyncMock()

            await on_schedule_updated(event)

            mock_llm.assert_not_called()
            mock_ws.broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_anomaly_detected_has_warning_severity(self):
        """Anomaly insights should have severity=warning."""
        event = Event(
            type="anomaly_detected",
            data={
                "channel_id": 0,
                "watts": 3500,
                "expected_watts": 1800,
            },
        )

        with patch("backend.llm.narrator.chat_completion", new_callable=AsyncMock) as mock_llm, \
             patch("backend.llm.narrator.ws_manager") as mock_ws, \
             patch("backend.llm.narrator.config") as mock_config:
            mock_llm.return_value = "Warning: unusual power on kitchen channel."
            mock_ws.broadcast = AsyncMock()
            mock_config.ELEVENLABS_TTS_ENABLED = False
            mock_config.ELEVENLABS_API_KEY = ""
            mock_config.LLM_NARRATOR_MODEL = "test"

            await on_anomaly_detected(event)

            call_args = mock_ws.broadcast.call_args[0][0]
            assert call_args["data"]["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_generate_insight_returns_fallback_on_error(self):
        """On LLM failure, should return a fallback message instead of raising."""
        with patch("backend.llm.narrator.chat_completion", new_callable=AsyncMock) as mock_llm, \
             patch("backend.llm.narrator.config") as mock_config:
            mock_llm.side_effect = Exception("API down")
            mock_config.LLM_NARRATOR_MODEL = "test"

            insight = await _generate_insight("test prompt", "test_cat", "info")

            assert insight["category"] == "test_cat"
            assert insight["severity"] == "info"
            assert isinstance(insight["message"], str)
            assert len(insight["message"]) > 0
