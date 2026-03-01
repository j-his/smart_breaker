"""Pydantic models for validating sensor readings from ESP32 hardware."""
from datetime import datetime, timezone

from pydantic import BaseModel, field_validator, model_validator
from backend import config


class ChannelReading(BaseModel):
    """A single channel reading from the breaker box.

    Hardware (ESP32) may send only channel_id + current_amps.
    Zone/appliance are filled from config defaults if not provided.
    """
    channel_id: int
    assigned_zone: str = ""
    assigned_appliance: str = ""
    current_amps: float
    power_watts: float | None = None  # Hardware may send pre-computed watts

    @model_validator(mode="before")
    @classmethod
    def fill_defaults(cls, data):
        """Fill zone/appliance from config if not provided by hardware."""
        if isinstance(data, dict):
            ch_id = data.get("channel_id", 0)
            if not data.get("assigned_zone") or not data.get("assigned_appliance"):
                assignments = config.DEFAULT_CHANNEL_ASSIGNMENTS
                default = assignments[ch_id] if ch_id < len(assignments) else {"zone": "unknown", "appliance": "unknown"}
                if not data.get("assigned_zone"):
                    data["assigned_zone"] = default["zone"]
                if not data.get("assigned_appliance"):
                    data["assigned_appliance"] = default["appliance"]
            # Auto-fill timestamp at the SensorReading level, not here
        return data

    def get_watts(self) -> float:
        """Return power in watts. Use power_watts if provided, else compute from amps."""
        if self.power_watts is not None:
            return self.power_watts
        return round(self.current_amps * config.VOLTAGE, 2)


class SensorReading(BaseModel):
    """A complete sensor reading with all 4 channels."""
    device_id: str
    timestamp: str = ""
    channels: list[ChannelReading]

    @model_validator(mode="before")
    @classmethod
    def fill_timestamp(cls, data):
        """Auto-fill timestamp if empty (ESP32 may not have accurate time)."""
        if isinstance(data, dict):
            if not data.get("timestamp"):
                data["timestamp"] = datetime.now(timezone.utc).isoformat()
        return data

    @field_validator("channels")
    @classmethod
    def must_have_4_channels(cls, v):
        if len(v) != config.NUM_CHANNELS:
            raise ValueError(f"Expected {config.NUM_CHANNELS} channels, got {len(v)}")
        return v

    def to_watts_list(self) -> list[float]:
        """Return [ch0_watts, ch1_watts, ch2_watts, ch3_watts]."""
        return [ch.get_watts() for ch in self.channels]

    def to_broadcast_dict(self, simulated: bool = False) -> dict:
        """Format for WebSocket broadcast matching iOS LiveChannel schema.

        iOS expects: assigned_zone, assigned_appliance, current_watts, is_active
        """
        return {
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "simulated": simulated,
            "channels": [
                {
                    "channel_id": ch.channel_id,
                    "assigned_zone": ch.assigned_zone,
                    "assigned_appliance": ch.assigned_appliance,
                    "current_watts": ch.get_watts(),
                    "is_active": ch.current_amps > 0.1,
                }
                for ch in self.channels
            ],
        }
