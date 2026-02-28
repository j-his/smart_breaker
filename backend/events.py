"""
Async pub-sub event bus for internal component communication.

Events flow: sensor_reading_arrived -> ml_inference_complete ->
schedule_updated -> calendar_update_broadcast -> insight_generated

Usage:
    bus = EventBus()
    bus.subscribe("sensor_reading", my_handler)
    await bus.publish("sensor_reading", {"channels": [...]})
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine
from collections import defaultdict

logger = logging.getLogger(__name__)

# ── Event Types (constants) ──────────────────────────────────────────────────
SENSOR_READING = "sensor_reading"
ML_INFERENCE_COMPLETE = "ml_inference_complete"
ANOMALY_DETECTED = "anomaly_detected"
SCHEDULE_UPDATED = "schedule_updated"
GRID_STATUS_CHANGED = "grid_status_changed"
CALENDAR_IMPORTED = "calendar_imported"
TASK_ADDED = "task_added"
SETTINGS_CHANGED = "settings_changed"

EventHandler = Callable[["Event"], Coroutine[Any, Any, None]]


@dataclass
class Event:
    """An event published on the bus."""
    type: str
    data: dict
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EventBus:
    """Simple async pub-sub. Handlers run concurrently via gather."""

    def __init__(self):
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)
        logger.debug("Subscribed %s to '%s'", handler.__name__, event_type)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        self._subscribers[event_type] = [
            h for h in self._subscribers[event_type] if h is not handler
        ]

    async def publish(self, event_type: str, data: dict) -> None:
        event = Event(type=event_type, data=data)
        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            return
        logger.debug("Publishing '%s' to %d handlers", event_type, len(handlers))
        results = await asyncio.gather(
            *(h(event) for h in handlers),
            return_exceptions=True,
        )
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Handler %s failed on '%s': %s",
                    handlers[i].__name__, event_type, result,
                )


# Singleton instance — import this in other modules
event_bus = EventBus()
