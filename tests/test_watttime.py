"""Tests for WattTime API client and GridCache WattTime integration."""
import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.grid.watttime import WattTimeClient


class TestWattTimeClient:
    """WattTime API client unit tests."""

    @pytest.mark.asyncio
    async def test_login_caches_token(self):
        """Login should cache the bearer token and reuse it."""
        client = WattTimeClient(
            username="testuser", password="testpass",
            base_url="https://api.watttime.org", region="CAISO_NORTH",
        )
        mock_response = MagicMock()
        mock_response.json.return_value = {"token": "abc123"}
        mock_response.raise_for_status = MagicMock()

        with patch("backend.grid.watttime.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            token = await client._login()
            assert token == "abc123"
            assert client._token == "abc123"

            # Second call to _get_token should NOT re-login (token is cached)
            mock_http.get.reset_mock()
            token2 = await client._get_token()
            assert token2 == "abc123"
            mock_http.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_login_refreshes_on_expiry(self):
        """Token should be refreshed when it expires."""
        client = WattTimeClient(
            username="testuser", password="testpass",
            base_url="https://api.watttime.org", region="CAISO_NORTH",
        )
        # Pre-set an expired token
        client._token = "old_token"
        client._token_expires = time.monotonic() - 1  # already expired

        mock_response = MagicMock()
        mock_response.json.return_value = {"token": "new_token"}
        mock_response.raise_for_status = MagicMock()

        with patch("backend.grid.watttime.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            token = await client._get_token()
            assert token == "new_token"
            assert client._token == "new_token"

    @pytest.mark.asyncio
    async def test_get_current_index_maps_to_schema(self):
        """get_current_index should convert MOER to gCO2/kWh."""
        client = WattTimeClient(
            username="testuser", password="testpass",
            base_url="https://api.watttime.org", region="CAISO_NORTH",
        )
        client._token = "valid_token"
        client._token_expires = time.monotonic() + 3600

        # Mock the signal-index response (MOER in lbs/MWh)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"value": 800}]  # 800 lbs CO2/MWh
        }
        mock_response.raise_for_status = MagicMock()

        with patch("backend.grid.watttime.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            result = await client.get_current_index()
            assert "carbon_intensity_gco2_kwh" in result
            assert "moer" in result
            # 800 lbs/MWh * 453.592 / 1000 = ~362.9 gCO2/kWh
            expected = round(800 * 453.592 / 1000, 1)
            assert result["carbon_intensity_gco2_kwh"] == expected

    @pytest.mark.asyncio
    async def test_fallback_on_api_error(self):
        """GridCache should fall back to local sim when WattTime API fails."""
        from backend.grid.cache import GridCache

        cache = GridCache(ttl_seconds=300)
        # Manually inject a failing WattTime client
        mock_wt = AsyncMock()
        mock_wt.get_current_index = AsyncMock(side_effect=Exception("API down"))
        cache._watttime = mock_wt

        # Should still return a valid snapshot (from local tou_rates)
        snapshot = await cache.get_current()
        assert "tou_price_cents_kwh" in snapshot
        assert "carbon_intensity_gco2_kwh" in snapshot
        assert "status" in snapshot
