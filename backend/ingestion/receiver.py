"""Sensor data receiver — validates, buffers, and publishes sensor readings."""
import logging

from backend.events import event_bus, SENSOR_READING
from backend.grid.cache import GridCache
from backend.ingestion.validator import SensorReading
from backend.ingestion.buffer import SensorBuffer
from backend.ingestion.fallback import HardwareFallback
from backend import config

logger = logging.getLogger(__name__)

# Module singletons
sensor_buffer = SensorBuffer(window_size=96, n_features=8)
hardware_fallback = HardwareFallback(timeout_s=config.HARDWARE_TIMEOUT_S)
grid_cache = GridCache()


async def process_sensor_reading(
    reading: SensorReading,
    simulated: bool = False,
) -> dict:
    """Validate, buffer, publish event, and return broadcast dict.

    Args:
        reading: Validated SensorReading from hardware or synthetic fallback
        simulated: True if this is synthetic data

    Returns:
        Dict formatted for WebSocket broadcast (iOS LiveChannel schema)
    """
    # Record real data arrival for fallback tracking
    if not simulated:
        hardware_fallback.record_real_data()

    # Build feature vector for ML buffer
    watts = reading.to_watts_list()
    total = sum(watts)
    grid = grid_cache.get_current()
    feature_vector = watts + [
        total,
        grid.get("renewable_pct", 0),
        grid.get("carbon_intensity_gco2_kwh", 0),
        grid.get("tou_price_cents_kwh", 0),
    ]
    sensor_buffer.add(feature_vector)

    # Publish event for other subsystems
    await event_bus.publish(SENSOR_READING, {
        "watts": watts,
        "total": total,
        "simulated": simulated,
    })

    # Return broadcast-ready dict
    broadcast = reading.to_broadcast_dict(simulated=simulated)
    logger.debug("Processed reading from %s (simulated=%s)", reading.device_id, simulated)
    return broadcast
