"""WattTime API client — async carbon intensity data with token caching."""
from __future__ import annotations

import logging
import time

import httpx

from backend import config

logger = logging.getLogger(__name__)

# MOER is in lbs CO2/MWh — convert to gCO2/kWh
_MOER_TO_GCO2_KWH = 453.592 / 1000


class WattTimeClient:
    """Async client for the WattTime v3 API.

    Handles Basic-auth login, bearer-token caching (25 min TTL),
    and conversion of MOER values to gCO2/kWh.
    """

    TOKEN_TTL_S = 25 * 60  # 25 minutes

    def __init__(
        self,
        username: str = "",
        password: str = "",
        base_url: str = "",
        region: str = "",
    ):
        self._username = username or config.WATTTIME_USERNAME
        self._password = password or config.WATTTIME_PASSWORD
        self._base_url = (base_url or config.WATTTIME_BASE_URL).rstrip("/")
        self._region = region or config.WATTTIME_REGION
        self._token: str | None = None
        self._token_expires: float = 0  # monotonic timestamp

    async def _login(self) -> str:
        """POST /login with Basic auth, return bearer token."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/login",
                auth=(self._username, self._password),
                timeout=10,
            )
            resp.raise_for_status()
            token = resp.json()["token"]
        self._token = token
        self._token_expires = time.monotonic() + self.TOKEN_TTL_S
        logger.debug("WattTime login successful, token cached for 25 min")
        return token

    async def _get_token(self) -> str:
        """Return cached token or refresh if expired."""
        if self._token and time.monotonic() < self._token_expires:
            return self._token
        return await self._login()

    async def get_current_index(self) -> dict:
        """Fetch latest carbon intensity for the configured region.

        Returns dict with at least: moer, carbon_intensity_gco2_kwh
        """
        token = await self._get_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/v3/signal-index",
                params={"region": self._region, "signal_type": "co2_moer"},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            resp.raise_for_status()
        data = resp.json()
        moer = data.get("data", [{}])[0].get("value", 0)
        return {
            "moer": moer,
            "carbon_intensity_gco2_kwh": round(moer * _MOER_TO_GCO2_KWH, 1),
        }

    async def get_forecast(self) -> list[dict]:
        """Fetch 24h carbon forecast for the configured region.

        Returns list of dicts with: hour, carbon_intensity_gco2_kwh
        """
        token = await self._get_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/v3/forecast",
                params={"region": self._region, "signal_type": "co2_moer"},
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            resp.raise_for_status()
        data = resp.json().get("data", [])
        result = []
        for i, point in enumerate(data[:24]):
            moer = point.get("value", 0)
            result.append({
                "hour": i,
                "carbon_intensity_gco2_kwh": round(moer * _MOER_TO_GCO2_KWH, 1),
            })
        return result
