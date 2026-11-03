import json

import pytest


def test_initial_and_regular_incoming_jobs_run_to_completion(run_simulation, base_config):
    base_config["Simulation"]["simulation_length"] = 21600
    base_config["Simulation"]["timestep"] = 1800
    base_config["jobs"]["initial_mix"] = {"GridPP": 1}
    base_config["jobs"]["regular_incoming_mix"] = {"GridPP": 1}
    base_config["jobs"]["incoming_timestep"] = 3600

    run = run_simulation(base_config, "initial_plus_refill")

    assert run.result.returncode == 0, run.result.stdout + run.result.stderr

    summary = json.loads((run.run_dir / "summary.json").read_text())

    assert summary["jobs"]["started"] == 4
    assert summary["jobs"]["finished"] == 2
    assert summary["jobs"]["total_cores_used"] == 4
    assert summary["cpu"]["total_core_seconds"] == 36000.0
    assert summary["duration"]["simulated_seconds"] == 21600.0
    assert summary["energy"]["total_kwh"] == pytest.approx(1.3)
    assert summary["energy"]["peaktime_kwh"] == pytest.approx(0.7)
    assert summary["carbon"]["total_g"] == pytest.approx(130.0)
    assert summary["carbon"]["peaktime_g"] == pytest.approx(70.0)
    assert summary["simulation_parameters"]["jobs"]["initial"] == {"GridPP": 1}
    assert summary["simulation_parameters"]["jobs"]["regular_incoming"] == [
        {
            "job_mix": {"GridPP": 1},
            "incoming_timestep_seconds": 3600,
        }
    ]


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
