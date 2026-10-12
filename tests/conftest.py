import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"


@pytest.fixture
def fixture_paths():
    return SimpleNamespace(
        carbon_dir=FIXTURES_DIR / "data" / "carbon_intensity",
        inventory_csv=FIXTURES_DIR / "data" / "cluster" / "minimal_inventory.csv",
        frequency_csv=FIXTURES_DIR / "data" / "cluster" / "minimal_frequency_dependence.csv",
        multifreq_frequency_csv=FIXTURES_DIR / "data" / "cluster" / "multifreq_frequency_dependence.csv",
    )


@pytest.fixture
def base_config(fixture_paths):
    config = json.loads((FIXTURES_DIR / "minimal_config.json").read_text())

    config["carbon_intensity"]["folder"] = f"{fixture_paths.carbon_dir}{os.sep}"
    config["cluster"]["inventory_csv"] = str(fixture_paths.inventory_csv)
    config["cluster"]["frequency_csv"] = str(fixture_paths.frequency_csv)

    return config


@pytest.fixture
def run_simulation(tmp_path):
    def _run(config, name):
        run_base_dir = tmp_path / f"runs_{name}"
        config["output"]["log_dir"] = str(run_base_dir)

        config_path = tmp_path / f"config_{name}.json"
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
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        run_dirs = sorted(run_base_dir.iterdir()) if run_base_dir.exists() else []
        run_dir = run_dirs[0] if run_dirs else None

        return SimpleNamespace(
            result=result,
            run_dirs=run_dirs,
            run_dir=run_dir,
        )

    return _run


@pytest.fixture
def minimal_config(tmp_path, fixture_paths):
    config = json.loads((FIXTURES_DIR / "minimal_config.json").read_text())
    run_base_dir = tmp_path / "runs"

    config["carbon_intensity"]["folder"] = f"{fixture_paths.carbon_dir}{os.sep}"
    config["cluster"]["inventory_csv"] = str(fixture_paths.inventory_csv)
    config["cluster"]["frequency_csv"] = str(fixture_paths.frequency_csv)
    config["output"]["log_dir"] = str(run_base_dir)

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n")

    return SimpleNamespace(
        path=config_path,
        data=config,
        run_base_dir=run_base_dir,
    )


@pytest.fixture
def completed_run(minimal_config):
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
            str(minimal_config.path),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    run_dirs = sorted(minimal_config.run_base_dir.iterdir()) if minimal_config.run_base_dir.exists() else []
    run_dir = run_dirs[0] if run_dirs else None

    return SimpleNamespace(
        config=minimal_config,
        result=result,
        run_dirs=run_dirs,
        run_dir=run_dir,
    )
