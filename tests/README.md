# Test Overview

All tests are integration tests under `tests/integration/`. They use the small deterministic
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

Both tests run one deterministic GridPP job on a node with three frequency steps
(`multifreq_frequency_dependence.csv`) over a 3-hour window (16:00–19:00) with 30-minute
timesteps, so the job outlives the simulation and every policy's totals are exactly
computable.

- **test_savings_policy_energy_and_carbon** — parametrized over `none`, `cd`, `cdcd`,
  `cd1721`, and `cdcd1721`; asserts the exact total and peak-time (5–9pm) energy and carbon
  for each policy, including that the 17:00 clock-down of the `cd1721`/`cdcd1721` policies
  takes effect from the 17:00 timestep onward.
- **test_highforecast_policy_clocks_down_while_forecast_is_high** — uses
  `highforecast_carbon_intensity.csv`, whose forecast rises above and later falls below the
  400±5 hysteresis band; asserts the exact totals produced by the one-timestep anticipation
  delay on either side of the high-forecast window (clock-down at 17:30, clock-up at 19:00).

## test_job_refill.py

- **test_regular_incoming_jobs_are_submitted_and_started** — runs 1 initial GridPP job plus
  an hourly `regular_incoming_mix` refill on a 2-thread node; the 17:00 refill starts while
  the later ones stay queued, so exactly 2 jobs start and none finish before the timeout,
  and the refill configuration is preserved in `summary.json`.

## test_default_config_reference.py

- **test_default_config_run_matches_reference_summary** — opt-in via
  `ORACLE_D_RUN_DEFAULT_REFERENCE_TEST=1`; runs the full 50k-job default config from fixture
  copies and compares the resulting `summary.json` to the reference output in
  `tests/fixtures/default/logs/runs/test/summary.json`, ignoring only wall-clock runtime
  fields.
