import io
from datetime import datetime, timedelta

import pytest

from util.Verification import report, verify_config

CARBON_HEADER = "datetime,forecast[gCO2e/kWh],actual[gCO2e/kWh],fracc,index,dataedit"


def _carbon_rows(start, end, step_minutes=30):
    rows = []
    timestamp = datetime.fromisoformat(start)
    while timestamp <= datetime.fromisoformat(end):
        rows.append(f"{timestamp:%Y-%m-%dT%H:%M:%S},100,100,0,n,")
        timestamp += timedelta(minutes=step_minutes)
    return rows


def _use_carbon_file(config, tmp_path, rows):
    (tmp_path / "carbon.csv").write_text("\n".join([CARBON_HEADER, *rows]) + "\n")
    config["carbon_intensity"]["folder"] = str(tmp_path)
    config["carbon_intensity"]["filename"] = "carbon.csv"


def _assert_error(result, *fragments):
    assert any(all(f in error for f in fragments) for error in result.errors), (
        f"no error containing {fragments}: {result.errors}"
    )


# ---------------------------------------------------------------------------
#   Valid configs and the loaded data
# ---------------------------------------------------------------------------


def test_minimal_config_passes_and_returns_the_loaded_data(base_config):
    result = verify_config(base_config)

    assert result.ok, result.errors
    assert result.start_time == "2024-01-16 16:00"
    assert sum(result.inventory.values()) == 1
    # 21600 s in 18000 s steps: the last update is at 16:00 + 2 * 5 h = 02:00.
    assert result.carbon_data[0][0] == "2024-01-16T16:00:00"
    assert result.carbon_data[-1][0] == "2024-01-17T02:00:00"


def test_quarter_hour_carbon_data_is_accepted(base_config, tmp_path):
    _use_carbon_file(
        base_config, tmp_path, _carbon_rows("2024-01-16T16:00", "2024-01-17T02:00", 15)
    )

    assert verify_config(base_config).ok


def test_clock_time_start_is_resolved_once(base_config):
    base_config["Simulation"]["desired_starttime"] = None

    result = verify_config(base_config, now=datetime(2024, 1, 16, 16, 7, 42))

    assert result.ok, result.errors
    assert result.start_time == "2024-01-16 16:07"


# ---------------------------------------------------------------------------
#   Config values
# ---------------------------------------------------------------------------


def test_missing_entries_are_listed_together(base_config):
    del base_config["jobs"]
    del base_config["Simulation"]["timestep"]

    result = verify_config(base_config)

    _assert_error(result, "Simulation.timestep", "jobs.initial_mix")


@pytest.mark.parametrize(
    "section, key, value, fragment",
    [
        ("Simulation", "timestep", 0, "Simulation.timestep"),
        ("Simulation", "simulation_length", 3600.5, "Simulation.simulation_length"),
        ("Simulation", "desired_starttime", "16.01.2024 16:00", "desired_starttime"),
        ("Simulation", "savings_policy", "None", "Simulation.savings_policy"),
        ("carbon_intensity", "high_CI_threshold", "400", "high_CI_threshold"),
        ("jobs", "initial_mix", {"GridPP": -1}, "jobs.initial_mix"),
    ],
)
def test_invalid_values_are_errors(base_config, section, key, value, fragment):
    base_config[section][key] = value

    _assert_error(verify_config(base_config), fragment)


def test_regular_incoming_jobs_need_a_positive_incoming_timestep(base_config):
    base_config["jobs"]["regular_incoming_mix"] = {"GridPP": 1}
    base_config["jobs"]["incoming_timestep"] = 0

    _assert_error(verify_config(base_config), "jobs.incoming_timestep")


def test_invalid_verbosity_only_warns(base_config):
    base_config["output"]["verbosity"] = "loud"

    result = verify_config(base_config)

    assert result.ok, result.errors
    assert any("'loud'" in warning for warning in result.warnings)


def test_all_problems_are_reported_together(base_config):
    base_config["Simulation"]["savings_policy"] = "sometimes"
    base_config["carbon_intensity"]["filename"] = "missing.csv"
    base_config["cluster"]["cluster_name"] = "NOPE"

    result = verify_config(base_config)

    assert len(result.errors) == 3
    _assert_error(result, "savings_policy")
    _assert_error(result, "carbon_intensity file cannot be read")
    _assert_error(result, "no worker nodes", "'NOPE'")


# ---------------------------------------------------------------------------
#   Cluster
# ---------------------------------------------------------------------------


def test_cluster_loader_errors_are_reported(base_config, tmp_path):
    base_config["cluster"]["inventory_csv"] = str(tmp_path / "missing.csv")

    _assert_error(verify_config(base_config), "cluster files cannot be loaded")


@pytest.mark.parametrize(
    "vo, cores, memory", [("ATLAS", 8, 16), ("LHCb", 8, 32), ("CMS", 8, 8)]
)
def test_jobs_that_fit_no_node_are_an_error(base_config, vo, cores, memory):
    # The minimal node has 2 threads and 8 GB.
    base_config["jobs"]["regular_incoming_mix"] = {vo: 1}

    _assert_error(
        verify_config(base_config), f"VO '{vo}'", f"{cores} core(s) and {memory} GB"
    )


# ---------------------------------------------------------------------------
#   Carbon-intensity file
# ---------------------------------------------------------------------------


def test_start_before_the_carbon_file_is_an_error(base_config):
    base_config["Simulation"]["desired_starttime"] = "2024-01-15 16:00"

    _assert_error(
        verify_config(base_config), "no row for the start segment 2024-01-15 16:00"
    )


def test_carbon_file_ending_before_the_last_update_is_an_error(base_config, tmp_path):
    # The window nominally ends at 22:00, but the second 5 h step runs the last update at 02:00.
    _use_carbon_file(
        base_config, tmp_path, _carbon_rows("2024-01-16T16:00", "2024-01-17T01:30")
    )

    result = verify_config(base_config)

    _assert_error(
        result,
        "ends at 2024-01-17 01:30",
        "last update of the run is at 2024-01-17 02:00",
    )
    assert result.carbon_data is None


@pytest.mark.parametrize(
    "edit, fragment",
    [
        (
            lambda rows: rows.__setitem__(4, "2024-01-16T18:00:00,100,,0,n,"),
            "line 6 (missing or invalid",
        ),
        (
            lambda rows: rows.__setitem__(4, "2024-01-16T18:00:00,-3,100,0,n,"),
            "line 6 (missing or invalid",
        ),
        (lambda rows: rows.__delitem__(4), "line 6 (gap of 1:00:00)"),
        (lambda rows: rows.insert(3, rows[2]), "line 5 (timestamp not after"),
    ],
)
def test_bad_rows_inside_the_window_are_errors(base_config, tmp_path, edit, fragment):
    rows = _carbon_rows("2024-01-16T16:00", "2024-01-17T02:00")
    edit(rows)
    _use_carbon_file(base_config, tmp_path, rows)

    result = verify_config(base_config)

    _assert_error(result, "bad rows inside the simulation window", fragment)
    assert result.carbon_data is None


def test_bad_rows_outside_the_window_are_ignored(base_config, tmp_path):
    rows = [
        "2024-01-16T15:30:00,,,0,n,",
        *_carbon_rows("2024-01-16T16:00", "2024-01-17T02:00"),
        "2024-01-17T02:30:00,,,0,n,",
    ]
    _use_carbon_file(base_config, tmp_path, rows)

    assert verify_config(base_config).ok


# ---------------------------------------------------------------------------
#   Report of passed checks
# ---------------------------------------------------------------------------


def test_every_check_of_a_valid_config_reports_a_success(base_config):
    result = verify_config(base_config)

    assert [status for status, _ in result.log] == ["OK"] * len(result.log)
    assert len(result.passed) == 15
    assert any("covers the run up to its last update" in m for m in result.passed)
    assert any("Jobs of VO 'GridPP'" in m for m in result.passed)


def test_failed_check_replaces_its_success(base_config):
    base_config["Simulation"]["savings_policy"] = "sometimes"

    result = verify_config(base_config)

    assert not any("savings_policy" in m for m in result.passed)
    assert [status for status, m in result.log if "savings_policy" in m] == ["ERROR"]


def test_report_lists_successes_only_when_asked(base_config):
    base_config["Simulation"]["savings_policy"] = "sometimes"
    result = verify_config(base_config)

    quiet, verbose = io.StringIO(), io.StringIO()
    report(result, stream=quiet)
    report(result, stream=verbose, show_passed=True)

    assert "OK:" not in quiet.getvalue()
    lines = verbose.getvalue().splitlines()
    # Outcomes keep the order of the checks: the policy error sits between the timestep and job lines.
    timestep, policy, jobs = (
        next(i for i, line in enumerate(lines) if text in line)
        for text in ("Simulation.timestep", "savings_policy", "jobs.initial_mix")
    )
    assert timestep < policy < jobs
    assert lines[policy].startswith("  ERROR:")
