import json

import pytest


def test_carbon_pointer_tracks_segments_with_timesteps_larger_than_a_segment(
    run_simulation, base_config
):
    # One hourly timestep spans two half-hour CI segments; the pointer must
    # catch up by more than one segment per update. The CI steps from 100 to
    # 500 at 17:30, so the five accounted steps (16:00-20:00) read
    # 100, 100, 500, 500, 500 at 0.2 kWh each.
    base_config["Simulation"]["simulation_length"] = 14400
    base_config["Simulation"]["timestep"] = 3600
    base_config["carbon_intensity"]["filename"] = "step_carbon_intensity.csv"

    run = run_simulation(base_config, "ci_pointer")

    assert run.result.returncode == 0, run.result.stdout + run.result.stderr

    summary = json.loads((run.run_dir / "summary.json").read_text())

    assert summary["energy"]["total_kwh"] == pytest.approx(1.0)
    assert summary["carbon"]["total_g"] == pytest.approx(340.0)
