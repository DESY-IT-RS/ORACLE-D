# Test Overview

The integration tests live under `tests/integration/`, the unit tests under `tests/unit/`. They use the small deterministic
fixtures in `tests/fixtures/` and write run output to pytest temporary directories, never to
`logs/runs/`. Shared fixtures (`fixture_paths`, `base_config`, `minimal_config`,
`completed_run`, `run_simulation`) live in `tests/conftest.py`; the simulation tests run
`src/Main.py` as a subprocess.

## test_cluster_loader.py

- **test_load_cluster_inventory_from_minimal_csvs** — loads the minimal inventory and
  frequency CSVs and checks the dynamically created `WorkerNode` subclass has the expected
  hostname, cores, RAM, idle power, frequencies, and HEPScore.
- **test_load_cluster_inventory_respects_cluster_filter** — a `cluster_name` that matches no
  inventory row yields an empty inventory.
- **test_load_cluster_inventory_strict_raises_on_malformed_frequency_entry** — a frequency
  entry with too few `_`-separated fields raises `ValueError` when `strict=True`.
- **test_load_cluster_inventory_lenient_skips_malformed_frequency_entry** — with
  `strict=False` the malformed entry is skipped while a valid entry in the same row is kept.
- **test_load_cluster_inventory_strict_raises_on_missing_frequency_data** — an inventory node
  with no matching frequency-dependence row raises `KeyError` when `strict=True`.
- **test_load_cluster_inventory_lenient_skips_node_without_frequency_data** — the same
  situation with `strict=False` skips the node and returns an empty inventory.
- **test_load_cluster_inventory_strict_raises_on_invalid_numeric_inventory_value** — a
  non-numeric value in a numeric inventory column raises `ValueError` when `strict=True`.
- **test_load_cluster_inventory_lenient_skips_invalid_numeric_inventory_value** — the same
  row with `strict=False` is skipped and returns an empty inventory.

## test_main_run.py

- **test_main_runs_with_explicit_config_and_writes_run_directory** — `python3 src/Main.py
  --config ...` exits with code 0 and creates a run directory containing `config.json`,
  `parameters.txt`, `simulation.log`, `summary.txt`, and `summary.json`.
- **test_main_help_documents_config_argument** — `--help` exits cleanly and documents the
  `--config` argument.

## test_simulation_outputs.py

- **test_summary_json_contains_expected_integration_metrics** — a minimal one-job run
  produces the exact expected job counts, simulated duration, CPU seconds, energy, and carbon
  in `summary.json`.
- **test_summary_json_preserves_simulation_parameters** — the `simulation_parameters` section
  of `summary.json` reproduces the configured start time, length, timestep, policy, cluster
  inventory, and job mix.

## test_savings_policies.py

All tests run one deterministic GridPP job on a node with three frequency steps
(`multifreq_frequency_dependence.csv`: 200 W, 100 W, 80 W), so the job outlives the
simulation and every policy's totals are exactly computable. Unless a test overrides it, the
window is 3 hours (16:00–19:00) with 30-minute timesteps. The time-of-day policies
(`cd1721`, `cdcd1721`, `middaymaxcd`) trigger when an update crosses the boundary time since
the previous update, so the timestepping tests choose start times and timesteps for which no
update lands exactly on the boundary.

- **test_savings_policy_energy_and_carbon** — parametrized over `none`, `cd`, `cdcd`,
  `cd1721`, and `cdcd1721`; asserts the exact total and peak-time (5–9pm) energy and carbon
  for each policy, including that the 17:00 clock-down of the `cd1721`/`cdcd1721` policies
  takes effect from the 17:00 timestep onward.
- **test_cd1721_triggers_when_no_update_lands_exactly_on_the_hour** — starts at 16:30 with
  1-hour timesteps, so updates land at 16:30, 17:30, …; asserts that the clock-down fires
  exactly once (at the 17:30 update, which crosses 17:00) and the resulting totals of
  0.6 kWh and 60 g.
- **test_cd1721_clocks_down_only_once_with_small_timesteps** — 5-minute timesteps over
  16:00–18:00; asserts that crossing 17:00 clocks down by exactly one frequency step, once
  (12 steps at 200 W, then 13 at 100 W), not once per update between 17:00 and 17:09.
- **test_middaymaxcd_triggers_when_no_update_lands_in_the_minute_window** — starts at 10:45
  with 1-hour timesteps (`minimal_carbon_intensity.csv` starts at 10:00 for this test); asserts that the 11:30 clock-to-minimum and the 15:30
  clock-to-maximum each fire exactly once, and the exact total and peak-time (11:30–15:30)
  energy and carbon (one step at 200 W, four at 80 W, one at 200 W).
- **test_highforecast_policy_clocks_down_while_forecast_is_high** — uses
  `highforecast_carbon_intensity.csv`, whose forecast rises above and later falls below the
  400±5 hysteresis band; asserts the exact totals produced by the one-timestep anticipation
  delay on either side of the high-forecast window (clock-down at 17:30, clock-up at 19:00).

## test_carbon_intensity.py

- **test_carbon_pointer_tracks_segments_with_timesteps_larger_than_a_segment** — uses
  `step_carbon_intensity.csv`, whose intensity steps from 100 to 500 gCO2e/kWh at 17:30, with
  1-hour timesteps over half-hour segments; asserts that the carbon-intensity pointer catches
  up by more than one segment per update, giving exact totals of 1.0 kWh and 340 g.

## test_job_refill.py

- **test_initial_and_regular_incoming_jobs_run_to_completion** — runs 1 initial GridPP job
  plus an hourly `regular_incoming_mix` refill on the 2-thread node over 6 hours
  (16:00–22:00) with 30-minute timesteps; the initial job and the 17:00 refill run, the
  later refills queue, and one queued refill starts as each running job finishes (21:00 and
  22:00). Asserts 4 started and 2 finished jobs (36000 core-seconds), the exact total
  (1.3 kWh, 130 g) and peak-time (0.7 kWh, 70 g) energy and carbon, and that both the initial
  and the refill job mix are preserved in `summary.json`.
- **test_regular_incoming_jobs_are_submitted_and_started** — runs 1 initial GridPP job plus
  an hourly `regular_incoming_mix` refill on a 2-thread node; the 17:00 refill starts while
  the later ones stay queued, so exactly 2 jobs start and none finish before the timeout,
  and the refill configuration is preserved in `summary.json`.

## test_job_queue.py

- **test_queued_job_starts_when_cores_are_freed** — runs 3 initial GridPP jobs (1 core,
  5 hours each) on the 2-thread node with a 12-hour limit (`minimal_carbon_intensity.csv`
  runs to 06:00 the next day for this test); asserts from `simulation.log` that
  two jobs start at 16:00 and the queued third job starts at 21:00, in the same update in
  which the first two finish, and that the run ends at 02:00 once nothing is running or
  queued (36000 simulated seconds, 3 started, 3 finished, 15 core-hours, 2.0 kWh, 200 g).

## test_default_config_reference.py

- **test_default_config_run_matches_reference_summary** — opt-in via
  `ORACLE_D_RUN_DEFAULT_REFERENCE_TEST=1`; runs the full 50k-job default config from fixture
  copies and compares the resulting `summary.json` to the reference output in
  `tests/fixtures/default/logs/runs/test/summary.json`, ignoring only wall-clock runtime
  fields.

## test_startup_verification.py

- **test_uncovered_carbon_window_aborts_before_creating_a_run_directory** — a start a day
  before `minimal_carbon_intensity.csv` begins makes `Main.py` exit with code 1, explain the
  missing start segment on stderr, and create no run directory.
- **test_all_config_errors_are_reported_in_one_run** — an invalid policy, a zero timestep, and
  an unknown `cluster_name` are all reported in the same run ("Found 3 error(s)").
- **test_verify_only_checks_without_running** — `--verify-only` exits with code 0 on the
  minimal config and creates no run directory.
- **test_verification_warnings_are_written_to_the_run_log** — an invalid verbosity is
  reported as a warning in `simulation.log` and the run still completes.
- **test_highforecast_reads_the_next_forecast_up_to_the_last_carbon_row** — with the last
  update exactly on the final row of `highforecast_carbon_intensity.csv` (19:30), the
  highforecast look-ahead runs without clamping; one step further is rejected because a
  20:00 row is needed.

## unit/test_verification.py

Calls `util.Verification.verify_config` directly on the minimal config, with small carbon
CSVs written to `tmp_path`:

- the minimal config passes and returns the inventory and the carbon rows from the start
  segment up to the first row at or after the last update (02:00 for 21600 s in 18000 s
  steps); 15-minute carbon data is accepted; a `null` start time is resolved once.
- missing entries are listed together; invalid timestep, length, start time, savings policy,
  threshold and job counts are errors; refills need a positive `incoming_timestep`; an invalid
  verbosity only warns; several problems are reported together.
- cluster loader errors are reported, and VOs whose largest job fits on no node type are
  errors.
- a start before the carbon file, a file ending before the last update, and missing,
  negative, gapped or duplicate rows inside the window are errors; bad rows outside the window
  are ignored.
