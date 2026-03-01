"""Tests for LLM context assembler."""
from backend.llm.context import build_system_prompt


class TestBuildSystemPrompt:
    """Tests for build_system_prompt()."""

    def test_returns_nonempty_with_no_args(self):
        """With no arguments, should still return a valid prompt."""
        prompt = build_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_contains_energyai_role(self):
        """Prompt should contain the EnergyAI role framing."""
        prompt = build_system_prompt()
        assert "EnergyAI" in prompt

    def test_with_sensor_state_includes_watts(self):
        """When sensor_state is provided, channel watts should appear."""
        sensor = {
            "channels": [
                {"channel_id": 0, "assigned_zone": "kitchen", "current_watts": 1500},
                {"channel_id": 1, "assigned_zone": "laundry", "current_watts": 2400},
            ],
            "total_watts": 3900,
        }
        prompt = build_system_prompt(sensor_state=sensor)
        assert "1500" in prompt
        assert "2400" in prompt
        assert "Current Power" in prompt

    def test_with_grid_status_includes_price(self):
        """When grid_status is provided, price and status should appear."""
        grid = {
            "tou_price_cents_kwh": 38,
            "status": "red",
            "renewable_pct": 25.0,
            "carbon_intensity_gco2_kwh": 320,
            "tou_period": "peak",
        }
        prompt = build_system_prompt(grid_status=grid)
        assert "38" in prompt
        assert "red" in prompt
        assert "Grid Conditions" in prompt

    def test_with_optimization_includes_event_titles(self):
        """When optimization is provided, event titles should appear."""
        opt = {
            "optimized_events": [
                {"title": "Run Dryer", "optimized_start_hour": 2},
                {"title": "Charge EV", "optimized_start_hour": 1},
            ],
            "total_savings_cents": 15.5,
            "total_carbon_avoided_g": 200,
        }
        prompt = build_system_prompt(optimization=opt)
        assert "Run Dryer" in prompt
        assert "Charge EV" in prompt
        assert "Current Schedule" in prompt
