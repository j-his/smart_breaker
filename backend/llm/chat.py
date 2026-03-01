"""LLM chat module — Groq-compatible AsyncOpenAI with graceful fallback."""
from __future__ import annotations

import logging
from typing import AsyncGenerator

from openai import AsyncOpenAI

from backend import config

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    """Return a singleton AsyncOpenAI client pointed at Groq."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=config.GROQ_API_KEY or "no-key",
            base_url=config.GROQ_BASE_URL,
        )
    return _client


async def chat_completion(
    user_message: str,
    system_prompt: str = "",
    model: str = config.LLM_CHAT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 500,
) -> str:
    """Single-turn chat completion. Returns LLM response text.

    Falls back to mock response when ENABLE_LLM is False or on API error.
    """
    if not config.ENABLE_LLM:
        return _mock_response(user_message)

    try:
        client = get_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.warning("LLM chat_completion failed, using mock: %s", e)
        return _mock_response(user_message)


async def chat_stream(
    user_message: str,
    system_prompt: str = "",
    model: str = config.LLM_CHAT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 500,
) -> AsyncGenerator[str, None]:
    """Streaming chat completion. Yields text chunks.

    Falls back to mock response yielded as a single chunk on error.
    """
    if not config.ENABLE_LLM:
        yield _mock_response(user_message)
        return

    try:
        client = get_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
    except Exception as e:
        logger.warning("LLM chat_stream failed, using mock: %s", e)
        yield _mock_response(user_message)


def _mock_response(user_message: str) -> str:
    """Generate a helpful mock response when LLM is unavailable."""
    msg = user_message.lower()
    if "save" in msg or "cost" in msg or "money" in msg:
        return (
            "Based on current TOU rates, shifting your dryer and EV charging "
            "to super off-peak hours (midnight-7 AM) could save approximately "
            "15-25 cents per kWh. I'd recommend scheduling these for 1-5 AM."
        )
    if "carbon" in msg or "green" in msg or "emission" in msg:
        return (
            "Solar generation peaks between 10 AM and 2 PM in your area, "
            "making midday the greenest time to run appliances. Carbon intensity "
            "drops to around 200 gCO2/kWh during these hours."
        )
    if "schedule" in msg or "when" in msg:
        return (
            "Your current schedule has the dryer at 6 PM (peak pricing). "
            "I can move it to 2 AM for maximum savings, or noon for lowest "
            "carbon emissions. Which priority matters more to you?"
        )
    return (
        "I'm EnergyAI, your smart home energy assistant. I can help you "
        "optimize your energy usage, reduce costs, and lower carbon emissions. "
        "Try asking about your current usage, savings opportunities, or schedule."
    )
