"""Tests for the async event bus."""
import pytest
import asyncio
from backend.events import EventBus, Event


@pytest.mark.asyncio
async def test_subscribe_and_publish():
    bus = EventBus()
    received = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe("sensor_reading", handler)
    await bus.publish("sensor_reading", {"power": 1234})

    assert len(received) == 1
    assert received[0].type == "sensor_reading"
    assert received[0].data["power"] == 1234


@pytest.mark.asyncio
async def test_multiple_subscribers():
    bus = EventBus()
    results_a, results_b = [], []

    async def handler_a(event: Event):
        results_a.append(event)

    async def handler_b(event: Event):
        results_b.append(event)

    bus.subscribe("test_event", handler_a)
    bus.subscribe("test_event", handler_b)
    await bus.publish("test_event", {"x": 1})

    assert len(results_a) == 1
    assert len(results_b) == 1


@pytest.mark.asyncio
async def test_no_cross_talk():
    bus = EventBus()
    received = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe("type_a", handler)
    await bus.publish("type_b", {"should_not": "arrive"})

    assert len(received) == 0


@pytest.mark.asyncio
async def test_event_has_timestamp():
    bus = EventBus()
    received = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe("test", handler)
    await bus.publish("test", {})

    assert received[0].timestamp is not None
