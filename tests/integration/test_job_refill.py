import json

import pytest


def test_regular_incoming_jobs_are_submitted_and_started(run_simulation, base_config):
    base_config["Simulation"]["simulation_length"] = 10800
    base_config["Simulation"]["timestep"] = 1800
    base_config["jobs"]["regular_incoming_mix"] = {"GridPP": 1}
    base_config["jobs"]["incoming_timestep"] = 3600

    run = run_simulation(base_config, "refill")

    assert run.result.returncode == 0, run.result.stdout + run.result.stderr

    summary = json.loads((run.run_dir / "summary.json").read_text())

    assert summary["jobs"]["started"] == 2
    assert summary["jobs"]["finished"] == 0
    assert summary["jobs"]["total_cores_used"] == 2
    assert summary["duration"]["simulated_seconds"] == 10800.0
    assert summary["energy"]["total_kwh"] == pytest.approx(0.70)
    assert summary["simulation_parameters"]["jobs"]["regular_incoming"] == [
        {
            "job_mix": {"GridPP": 1},
            "incoming_timestep_seconds": 3600,
        }
    ]
