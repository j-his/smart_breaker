"""
Central configuration for EnergyAI backend.

All settings, API keys, model hyperparameters, and feature flags.
Reads from environment variables with sensible defaults.
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from project root only (do not search parent directories)
load_dotenv(BASE_DIR / ".env")

# ── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = DATA_DIR / "checkpoints"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# ── Hardware ─────────────────────────────────────────────────────────────────
VOLTAGE = 120  # volts — hardware sends amps only, we multiply
NUM_CHANNELS = 4
SENSOR_PUSH_INTERVAL_S = 100  # hardware pushes every ~100 seconds (0.01 Hz)
HARDWARE_TIMEOUT_S = 300  # fall back to mock after 5 min of no data

# ── Model Profiles ───────────────────────────────────────────────────────────
MODEL_PROFILE = os.getenv("MODEL_PROFILE", "cpu")  # "cpu" or "gpu"


@dataclass(frozen=True)
class ModelConfig:
    d_model: int
    n_heads: int
    n_encoder_layers: int
    n_decoder_layers: int
    d_ff: int
    dropout: float
    past_window: int       # timesteps of history (at 15-min resolution)
    forecast_horizon: int  # timesteps to predict (at 1-hr resolution)
    n_channels: int
    n_quantiles: int
    n_day_types: int
    n_appliance_types: int
    latent_dim: int        # VAE latent for anomaly head


MODEL_CONFIGS = {
    "cpu": ModelConfig(
        d_model=64,
        n_heads=8,
        n_encoder_layers=2,
        n_decoder_layers=2,
        d_ff=128,
        dropout=0.1,
        past_window=96,        # 96 x 15min = 24 hours
        forecast_horizon=24,   # 24 x 1hr = 24 hours
        n_channels=NUM_CHANNELS,
        n_quantiles=3,         # p10, p50, p90
        n_day_types=4,         # workday, weekend, wfh, away
        n_appliance_types=8,
        latent_dim=16,
    ),
    "gpu": ModelConfig(
        d_model=192,
        n_heads=12,
        n_encoder_layers=4,
        n_decoder_layers=4,
        d_ff=384,
        dropout=0.1,
        past_window=96,
        forecast_horizon=24,
        n_channels=NUM_CHANNELS,
        n_quantiles=3,
        n_day_types=4,
        n_appliance_types=8,
        latent_dim=32,
    ),
}


def get_model_config() -> ModelConfig:
    return MODEL_CONFIGS[MODEL_PROFILE]


# ── Training ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class TrainConfig:
    epochs: int = 80
    batch_size: int = 32
    lr: float = 1e-3
    weight_decay: float = 1e-5
    grad_clip: float = 1.0
    val_days: int = 10          # last N days for validation
    patience: int = 10          # early stopping patience
    checkpoint_path: str = str(MODEL_DIR / "model.pt")


TRAIN = TrainConfig()

# ── Synthetic Data ───────────────────────────────────────────────────────────
SYNTH_DAYS = 60
SYNTH_RESOLUTION_MIN = 1  # generate at 1-min, downsample later
SYNTH_OUTPUT = DATA_DIR / "synthetic_household.parquet"
SYNTH_CALENDARS_DIR = DATA_DIR / "calendars"

# ── Grid / TOU ───────────────────────────────────────────────────────────────
WATTTIME_USERNAME = os.getenv("WATTTIME_USERNAME", "")
WATTTIME_PASSWORD = os.getenv("WATTTIME_PASSWORD", "")
WATTTIME_REGION = os.getenv("WATTTIME_REGION", "CAISO_NORTH")
WATTTIME_BASE_URL = "https://api.watttime.org"
GRID_CACHE_TTL_S = 300  # 5 minutes

# ── LLM (Groq) ──────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
LLM_CHAT_MODEL = os.getenv("LLM_CHAT_MODEL", "openai/gpt-oss-120b")
LLM_NARRATOR_MODEL = os.getenv("LLM_NARRATOR_MODEL", "openai/gpt-oss-20b")
LLM_MAX_CONTEXT_TOKENS = 8000
LLM_CACHE_TTL_S = 60

# ── ElevenLabs TTS ───────────────────────────────────────────────────────────
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_flash_v2_5")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
ELEVENLABS_TTS_ENABLED = os.getenv("ELEVENLABS_TTS_ENABLED", "false").lower() == "true"
ELEVENLABS_OUTPUT_FORMAT = "mp3_44100_128"

# ── Optimizer ────────────────────────────────────────────────────────────────
OPTIMIZER_RERUN_INTERVAL_S = 900  # every 15 minutes
MAX_BREAKER_KW = 7.2              # 60A x 120V breaker limit
DEFAULT_ALPHA = 0.5               # cost weight
DEFAULT_BETA = 0.5                # carbon weight
MONTE_CARLO_ITERATIONS = 100

# ── Inference ────────────────────────────────────────────────────────────────
INFERENCE_DEBOUNCE_S = 120  # run inference every 2 minutes

# ── Security ────────────────────────────────────────────────────────────────
API_SECRET = os.getenv("API_SECRET", "")
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]

# ── WebSocket ────────────────────────────────────────────────────────────────
WS_HEARTBEAT_S = 30

# ── Demo Mode ────────────────────────────────────────────────────────────────
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
DEMO_TIME_SCALE = 900  # 1 real second = 15 simulated minutes

# ── Feature Flags ────────────────────────────────────────────────────────────
ENABLE_LLM = os.getenv("ENABLE_LLM", "true").lower() == "true"
ENABLE_WATTTIME = bool(WATTTIME_USERNAME and WATTTIME_PASSWORD)
ENABLE_HARDWARE_RELAY = os.getenv("ENABLE_RELAY", "false").lower() == "true"

# ── Channel Assignment Defaults (demo) ───────────────────────────────────────
DEFAULT_CHANNEL_ASSIGNMENTS = [
    {"channel_id": 0, "zone": "kitchen", "appliance": "inductive_stove"},
    {"channel_id": 1, "zone": "laundry_room", "appliance": "dryer"},
    {"channel_id": 2, "zone": "garage", "appliance": "ev_charger"},
    {"channel_id": 3, "zone": "bedroom", "appliance": "air_conditioning"},
]

# ── Appliance Power Estimates (watts) ────────────────────────────────────────
APPLIANCE_WATTS = {
    "inductive_stove": 1800,
    "dryer": 2400,
    "ev_charger": 3600,
    "air_conditioning": 1800,
    "water_heater": 4500,
    "dishwasher": 1200,
    "oven": 2500,
    "lighting": 200,
}

# ── Appliance Deferrability Defaults ─────────────────────────────────────────
DEFERRABLE_APPLIANCES = {"dryer", "ev_charger", "dishwasher", "water_heater"}
NON_DEFERRABLE_APPLIANCES = {"inductive_stove", "oven", "air_conditioning", "lighting"}

# ── Appliance Scheduling Windows (hour-of-day bounds) ────────────────────────
# (earliest_hour, latest_end_hour) — optimizer won't schedule outside these
APPLIANCE_TIME_WINDOWS: dict[str, tuple[int, int]] = {
    "dryer": (7, 22),            # 7am - 10pm
    "ev_charger": (0, 24),       # anytime (overnight charging is fine)
    "dishwasher": (7, 23),       # 7am - 11pm
    "water_heater": (5, 23),     # 5am - 11pm
    "inductive_stove": (6, 21),  # 6am - 9pm (non-deferrable, reference only)
    "oven": (6, 21),             # 6am - 9pm (non-deferrable, reference only)
    "air_conditioning": (6, 23), # 6am - 11pm (non-deferrable, reference only)
    "lighting": (6, 24),         # 6am - midnight (non-deferrable, reference only)
}
