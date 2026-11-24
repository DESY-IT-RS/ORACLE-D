import os
import subprocess
import sys

from conftest import PROJECT_ROOT


def test_uncovered_carbon_window_aborts_before_creating_a_run_directory(
    run_simulation, base_config
):
    # The carbon fixture starts on 2024-01-16 10:00, so a start a day earlier
    # cannot be covered and the run must stop before writing anything.
    base_config["Simulation"]["desired_starttime"] = "2024-01-15 16:00"

    run = run_simulation(base_config, "ci_uncovered")

    assert run.result.returncode == 1, run.result.stdout + run.result.stderr
    assert "no row for the start segment" in run.result.stderr
    assert "the simulation was not started" in run.result.stderr
    assert run.run_dirs == []


def test_all_config_errors_are_reported_in_one_run(run_simulation, base_config):
    base_config["Simulation"]["savings_policy"] = "sometimes"
    base_config["Simulation"]["timestep"] = 0
    base_config["cluster"]["cluster_name"] = "NOPE"

    run = run_simulation(base_config, "many_errors")

    assert run.result.returncode == 1
    assert "Simulation.savings_policy" in run.result.stderr
    assert "Simulation.timestep" in run.result.stderr
    assert "no worker nodes" in run.result.stderr
    assert "Found 3 error(s)" in run.result.stderr
    assert run.run_dirs == []


def test_verify_only_checks_without_running(tmp_path, minimal_config):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(PROJECT_ROOT / "src"), env.get("PYTHONPATH", "")]
    )

    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "src" / "Main.py"),
            "--config",
            str(minimal_config.path),
            "--verify-only",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "  OK: Simulation.timestep: 18000 s." in result.stdout
    assert "  OK: The carbon_intensity file covers the run" in result.stdout
    assert "ERROR" not in result.stdout
    assert result.stdout.rstrip().endswith("passed.")
    assert not minimal_config.run_base_dir.exists()


def test_verification_warnings_are_written_to_the_run_log(run_simulation, base_config):
    base_config["output"]["verbosity"] = "loud"

    run = run_simulation(base_config, "warning_logged")

    assert run.result.returncode == 0, run.result.stdout + run.result.stderr
    log = (run.run_dir / "simulation.log").read_text()
    assert "Invalid output.verbosity 'loud'" in log


def test_highforecast_reads_the_next_forecast_up_to_the_last_carbon_row(
    run_simulation, base_config, fixture_paths
):
    # The highforecast fixture ends at 19:30 and the last update lands exactly
    # there. The verification guarantees a row at or after the last update, so
    # the look-ahead to the next segment needs no clamping at the end of the data.
    base_config["Simulation"]["simulation_length"] = 12600
    base_config["Simulation"]["timestep"] = 1800
    base_config["Simulation"]["savings_policy"] = "highforecast"
    base_config["carbon_intensity"]["filename"] = "highforecast_carbon_intensity.csv"
    base_config["cluster"]["frequency_csv"] = str(fixture_paths.multifreq_frequency_csv)

    run = run_simulation(base_config, "highforecast_edge")

    assert run.result.returncode == 0, run.result.stdout + run.result.stderr

    # One step further needs a 20:00 row the fixture does not have.
    base_config["Simulation"]["simulation_length"] = 14400

    run = run_simulation(base_config, "highforecast_past_edge")

    assert run.result.returncode == 1
    assert "last update of the run is at 2024-01-16 20:00" in run.result.stderr
