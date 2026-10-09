import json
import os
import subprocess
import sys
from pathlib import Path

try:
    import pytest
except ImportError:
    pytest = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "default"
DEFAULT_CONFIG_PATH = DEFAULT_FIXTURE_DIR / "config.json"
REFERENCE_RUN_DIR = DEFAULT_FIXTURE_DIR / "logs" / "runs" / "test"
RUN_REFERENCE_TEST_ENV = "ORACLE_D_RUN_DEFAULT_REFERENCE_TEST"
ENABLED_VALUES = {"1", "true", "yes", "on"}
RUNTIME_ONLY_KEYS = {
    ("duration", "real_seconds"),
    ("duration", "real_minutes"),
}


def _reference_test_enabled():
    return os.environ.get(RUN_REFERENCE_TEST_ENV, "").lower() in ENABLED_VALUES


def _strip_runtime_only_fields(value, path=()):
    if isinstance(value, dict):
        return {
            key: _strip_runtime_only_fields(child, (*path, key))
            for key, child in value.items()
            if (*path, key) not in RUNTIME_ONLY_KEYS
        }

    if isinstance(value, list):
        return [_strip_runtime_only_fields(child, path) for child in value]

    return value


def test_default_config_run_matches_reference_summary(tmp_path):
    if not _reference_test_enabled():
        if pytest is not None:
            pytest.skip(
                f"Set {RUN_REFERENCE_TEST_ENV}=1 to run the default config reference test."
            )
        return

    assert DEFAULT_CONFIG_PATH.is_file(), (
        "Missing default config fixture at tests/fixtures/default/config.json"
    )
    reference_summary_path = REFERENCE_RUN_DIR / "summary.json"
    assert reference_summary_path.is_file(), (
        "Missing reference summary at tests/fixtures/default/logs/runs/test/summary.json"
    )

    run_base_dir = tmp_path / "runs"
    config = json.loads(DEFAULT_CONFIG_PATH.read_text())
    config["output"]["log_dir"] = str(run_base_dir)
    config["output"].pop("run_dir", None)

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n")

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(PROJECT_ROOT / "src"),
            env.get("PYTHONPATH", ""),
        ]
    )

    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "src" / "Main.py"),
            "--config",
            str(config_path),
        ],
        cwd=DEFAULT_FIXTURE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    new_run_dirs = sorted(path for path in run_base_dir.iterdir() if path.is_dir())

    assert len(new_run_dirs) == 1
    run_dir = new_run_dirs[0]
    assert run_dir.name.endswith("_rf20pmtest_50000gridpp_base")

    summary_path = run_dir / "summary.json"
    assert summary_path.is_file()

    actual_summary = json.loads(summary_path.read_text())
    reference_summary = json.loads(reference_summary_path.read_text())

    assert _strip_runtime_only_fields(actual_summary) == _strip_runtime_only_fields(
        reference_summary
    )
