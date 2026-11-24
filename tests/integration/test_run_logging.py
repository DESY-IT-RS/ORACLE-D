def test_low_verbosity_logs_the_lifecycle_and_summary_only(run_simulation, base_config):
    run = run_simulation(base_config, "verbosity_low")

    assert run.result.returncode == 0, run.result.stdout + run.result.stderr
    log = (run.run_dir / "simulation.log").read_text()
    stdout = run.result.stdout

    for output in (log, stdout):
        assert "Created simulation with parameters:" in output
        assert "No jobs left to run or queue; ending the simulation at" in output
        assert "Jobs Started                               : 1" in output
    # Events and per-job lines are finer than low.
    assert "Simulation day" not in log + stdout
    assert "Starting job" not in log + stdout
    # The data outputs do not depend on the verbosity.
    assert (run.run_dir / "parameters.txt").is_file()
    summary_txt = (run.run_dir / "summary.txt").read_text()
    assert "Jobs Started                               : 1" in summary_txt


def test_high_verbosity_keeps_job_lines_out_of_the_terminal(
    run_simulation, base_config
):
    base_config["output"]["verbosity"] = "high"

    run = run_simulation(base_config, "verbosity_high")

    assert run.result.returncode == 0, run.result.stdout + run.result.stderr
    log = (run.run_dir / "simulation.log").read_text()

    assert "DETAIL" in log and "Starting job GridPP-1 on node TESTNODE_0-001" in log
    assert "EVENT" in log and "Simulation day 1: 16/01/2024" in log
    assert "Simulation day 1: 16/01/2024" in run.result.stdout
    assert "Starting job" not in run.result.stdout


def test_frequency_change_is_logged_once_for_the_whole_cluster(
    run_simulation, base_config
):
    # The minimal node has a single frequency, so cdcd cannot clock it down: one
    # line for the cluster instead of one per node and step.
    base_config["Simulation"]["savings_policy"] = "cdcd"
    base_config["output"]["verbosity"] = "medium"

    run = run_simulation(base_config, "already_at_limit")

    assert run.result.returncode == 0, run.result.stdout + run.result.stderr
    log = (run.run_dir / "simulation.log").read_text()
    assert log.count("clocking down 2 step(s) for the whole run") == 1
    assert "(1 nodes, 1 of them already at that limit)" in log
    assert "already running at its lowest frequency" not in log + run.result.stdout
