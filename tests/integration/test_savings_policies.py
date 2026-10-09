import json

import pytest


def _policy_config(base_config, fixture_paths, savings_policy):
    base_config["Simulation"]["simulation_length"] = 10800
    base_config["Simulation"]["timestep"] = 1800
    base_config["Simulation"]["savings_policy"] = savings_policy
    base_config["cluster"]["frequency_csv"] = str(fixture_paths.multifreq_frequency_csv)
    return base_config


@pytest.mark.parametrize(
    "savings_policy, total_kwh, total_g, peaktime_kwh, peaktime_g",
    [
        ("none", 0.70, 70.0, 0.40, 40.0),
        ("cd", 0.35, 35.0, 0.20, 20.0),
        ("cdcd", 0.28, 28.0, 0.16, 16.0),
        ("cd1721", 0.45, 45.0, 0.20, 20.0),
        ("cdcd1721", 0.40, 40.0, 0.16, 16.0),
    ],
)
def test_savings_policy_energy_and_carbon(
    run_simulation,
    base_config,
    fixture_paths,
    savings_policy,
    total_kwh,
    total_g,
    peaktime_kwh,
    peaktime_g,
):
    config = _policy_config(base_config, fixture_paths, savings_policy)

    run = run_simulation(config, savings_policy)

    assert run.result.returncode == 0, run.result.stdout + run.result.stderr

    summary = json.loads((run.run_dir / "summary.json").read_text())

    assert summary["simulation_parameters"]["savings_policy"] == savings_policy
    assert summary["jobs"]["started"] == 1
    assert summary["jobs"]["finished"] == 0
    assert summary["duration"]["simulated_seconds"] == 10800.0
    assert summary["energy"]["total_kwh"] == pytest.approx(total_kwh)
    assert summary["energy"]["peaktime_kwh"] == pytest.approx(peaktime_kwh)
    assert summary["carbon"]["total_g"] == pytest.approx(total_g)
    assert summary["carbon"]["peaktime_g"] == pytest.approx(peaktime_g)


def test_highforecast_policy_clocks_down_while_forecast_is_high(
    run_simulation, base_config, fixture_paths
):
    config = _policy_config(base_config, fixture_paths, "highforecast")
    config["carbon_intensity"]["filename"] = "highforecast_carbon_intensity.csv"

    run = run_simulation(config, "highforecast")

    assert run.result.returncode == 0, run.result.stdout + run.result.stderr

    summary = json.loads((run.run_dir / "summary.json").read_text())

    assert summary["jobs"]["started"] == 1
    assert summary["jobs"]["finished"] == 0
    assert summary["energy"]["total_kwh"] == pytest.approx(0.55)
    assert summary["energy"]["peaktime_kwh"] == pytest.approx(0.25)
    assert summary["carbon"]["total_g"] == pytest.approx(55.0)
    assert summary["carbon"]["peaktime_g"] == pytest.approx(25.0)
