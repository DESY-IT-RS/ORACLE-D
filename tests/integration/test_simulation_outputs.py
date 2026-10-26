import json

import pytest


def test_summary_json_contains_expected_integration_metrics(completed_run):
    assert completed_run.result.returncode == 0, (
        completed_run.result.stdout + completed_run.result.stderr
    )

    summary = json.loads((completed_run.run_dir / "summary.json").read_text())

    assert summary["jobs"]["started"] == 1
    assert summary["jobs"]["finished"] == 1
    assert summary["jobs"]["total_cores_used"] == 1
    assert summary["duration"]["simulated_seconds"] == 18000.0
    assert summary["cpu"]["total_core_seconds"] == 18000.0
    assert summary["energy"]["total_kwh"] == pytest.approx(1.0)
    assert summary["carbon"]["total_g"] == pytest.approx(100.0)
    assert summary["carbon"]["peaktime_g"] == pytest.approx(0.0)


def test_summary_is_written_when_no_jobs_were_submitted(run_simulation, base_config):
    # An empty job mix ends the simulation on the first update; the summary
    # must still be written with zeroed averages instead of dividing by zero.
    base_config["jobs"]["initial_mix"] = {}

    run = run_simulation(base_config, "no_jobs")

    assert run.result.returncode == 0, run.result.stdout + run.result.stderr

    summary = json.loads((run.run_dir / "summary.json").read_text())

    assert summary["jobs"]["started"] == 0
    assert summary["jobs"]["finished"] == 0
    assert summary["duration"]["simulated_seconds"] == 0.0
    assert summary["energy"]["total_kwh"] == 0
    assert summary["energy"]["average_per_job_wh"] == 0
    assert summary["cpu"]["average_core_hours"] == 0
    assert summary["carbon"]["average_per_job_g"] == 0
    assert summary["carbon"]["peaktime_percent"] == 0
    assert summary["occupancy"]["average_fraction"] == 0


def test_summary_json_preserves_simulation_parameters(completed_run):
    assert completed_run.result.returncode == 0, (
        completed_run.result.stdout + completed_run.result.stderr
    )

    summary = json.loads((completed_run.run_dir / "summary.json").read_text())
    parameters = summary["simulation_parameters"]

    assert parameters["start_time"] == "2024-01-16 16:00:00"
    assert parameters["simulation_length_seconds"] == 21600
    assert parameters["timestep_seconds"] == 18000
    assert parameters["savings_policy"] == "none"
    assert parameters["cluster"]["worker_nodes"] == 1
    assert parameters["cluster"]["worker_cores"] == 2
    assert parameters["cluster"]["worker_node_inventory"] == {
        "TESTNODE_0": 1,
    }
    assert parameters["jobs"]["initial"] == {
        "GridPP": 1,
    }
    assert parameters["jobs"]["regular_incoming"] == []
