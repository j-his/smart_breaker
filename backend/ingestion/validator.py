"""Pydantic models for validating sensor readings from ESP32 hardware."""
from pydantic import BaseModel, field_validator
from backend import config


class ChannelReading(BaseModel):
    """A single channel reading from the breaker box."""
    channel_id: int
    assigned_zone: str
    assigned_appliance: str
    current_amps: float

    @property
    def power_watts(self) -> float:
        """Convert amps to watts using configured voltage (120V)."""
        return round(self.current_amps * config.VOLTAGE, 2)


class SensorReading(BaseModel):
    """A complete sensor reading with all 4 channels."""
    device_id: str
    timestamp: str
    channels: list[ChannelReading]

    @field_validator("channels")
    @classmethod
    def must_have_4_channels(cls, v):
        if len(v) != config.NUM_CHANNELS:
            raise ValueError(f"Expected {config.NUM_CHANNELS} channels, got {len(v)}")
        return v

    def to_watts_list(self) -> list[float]:
        """Return [ch0_watts, ch1_watts, ch2_watts, ch3_watts]."""
        return [ch.power_watts for ch in self.channels]

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
                    "current_watts": ch.power_watts,
                    "is_active": ch.current_amps > 0.1,
                }
                for ch in self.channels
            ],
        }
