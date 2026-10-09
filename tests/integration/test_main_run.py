def test_main_runs_with_explicit_config_and_writes_run_directory(completed_run):
    assert completed_run.result.returncode == 0, (
        completed_run.result.stdout + completed_run.result.stderr
    )
    assert len(completed_run.run_dirs) == 1

    run_dir = completed_run.run_dir
    assert run_dir.name.endswith("_integration_test")
    assert (run_dir / "config.json").is_file()
    assert (run_dir / "parameters.txt").is_file()
    assert (run_dir / "simulation.log").is_file()
    assert (run_dir / "summary.txt").is_file()
    assert (run_dir / "summary.json").is_file()


def test_main_help_documents_config_argument():
    import subprocess
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            str(project_root / "src" / "Main.py"),
            "--help",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0
    assert "--config CONFIG" in result.stdout
