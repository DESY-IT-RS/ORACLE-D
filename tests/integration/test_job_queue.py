import json

import pytest


def test_queued_job_starts_when_cores_are_freed(run_simulation, base_config):
    # Three 5-hour GridPP jobs (1 core each) on the 2-thread test node: two start
    # at 16:00, the third waits in the queue and starts at 21:00, in the same
    # update in which the first two finish. The run must not end while a job is
    # queued, and ends at 02:00 once the queue is empty and nothing is running,
    # well before the 12-hour limit.
    base_config["Simulation"]["simulation_length"] = 43200
    base_config["Simulation"]["timestep"] = 1800
    base_config["carbon_intensity"]["filename"] = "overnight_carbon_intensity.csv"
    base_config["jobs"]["initial_mix"] = {"GridPP": 3}
    base_config["output"]["verbosity"] = "high"

    run = run_simulation(base_config, "queue")

    assert run.result.returncode == 0, run.result.stdout + run.result.stderr

    log = (run.run_dir / "simulation.log").read_text()

    assert "Starting job GridPP-1 on node TESTNODE_0-001 at 2024-01-16 16:00:00" in log
    assert "Starting job GridPP-2 on node TESTNODE_0-001 at 2024-01-16 16:00:00" in log
    assert "Starting job GridPP-3 on node TESTNODE_0-001 at 2024-01-16 21:00:00" in log
    assert "Job GridPP-3 finished on node TESTNODE_0-001 at 2024-01-17 02:00:00" in log

    summary = json.loads((run.run_dir / "summary.json").read_text())

    assert summary["jobs"]["started"] == 3
    assert summary["jobs"]["finished"] == 3
    assert summary["duration"]["simulated_seconds"] == 36000.0
    assert summary["cpu"]["total_core_hours"] == pytest.approx(15.0)
    # The single physical core is saturated by one job, so every accounted
    # step (16:00-01:30, 20 steps) draws the full 200 W.
    assert summary["energy"]["total_kwh"] == pytest.approx(2.0)
    assert summary["carbon"]["total_g"] == pytest.approx(200.0)
