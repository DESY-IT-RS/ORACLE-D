# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY
#                     and the University of Glasgow
# Authors: Dwayne Spiteri and Gordon Stewart.
# For more information about rights and fair use please refer to src/Main.py.
# For full detailed and legal infomration please read the LICENSE and NOTICE
#    files in the main directory
# ===========================================================================

"""Start-up verification of the configuration and the input data files.

``verify_config`` collects every problem that would otherwise make a run hang,
crash part-way, or silently produce wrong numbers. The simulation only starts
when no errors were found, and it uses the inventory and carbon data loaded
here, so the checked data is the data that is simulated.
"""

from __future__ import annotations

import csv
import math
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from cluster.ClusterLoader import load_cluster_inventory
from jobs.VOJobFactory import (
    ATLASJobFactory,
    GridPPJobFactory,
    LHCbJobFactory,
    VOJobFactory,
)
from simulation.Time import SimulationTime
from util import Logging

START_TIME_FORMAT = "%Y-%m-%d %H:%M"
CARBON_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S"
# Rows are half-hourly segments; finer data (e.g. 15 min) is fine, coarser data is not.
MAX_CARBON_ROW_SPACING = timedelta(minutes=30)

REQUIRED_KEYS = {
    "Simulation": (
        "desired_starttime",
        "simulation_length",
        "timestep",
        "savings_policy",
    ),
    "carbon_intensity": ("folder", "filename", "high_CI_threshold"),
    "cluster": ("cluster_name", "inventory_csv", "frequency_csv", "strict"),
    "jobs": ("initial_mix", "regular_incoming_mix"),
}

VALID_SAVINGS_POLICIES = (
    "none",
    "cd",
    "cdcd",
    "cd1721",
    "cdcd1721",
    "middaymaxcd",
    "highforecast",
)

# Largest job each VO factory can create: (cores, GB per core).
# The core counts mirror the __require_cores methods in jobs/VOJobFactory.py.
LARGEST_JOB_BY_VO = {
    "ATLAS": (8, ATLASJobFactory("")._memory_required_GB_per_core),
    "LHCb": (8, LHCbJobFactory("")._memory_required_GB_per_core),
    "GridPP": (1, GridPPJobFactory("")._memory_required_GB_per_core),
}
LARGEST_GENERIC_JOB = (8, VOJobFactory("")._memory_required_GB_per_core)


@dataclass
class VerificationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Filled in when the corresponding checks pass.
    start_time: str | None = None
    inventory: dict | None = None
    carbon_data: list[list[str]] | None = None

    @property
    def ok(self):
        return not self.errors


def _is_count(value, minimum):
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _parse_float(raw):
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def last_update_time(start, simulation_length, timestep):
    """Time of the last Cluster.update(): the loop stops after the first update at or past the end."""
    steps = math.ceil(simulation_length / timestep)
    return start + timedelta(seconds=steps * timestep)


def verify_config(config, now=None):
    """Check the config and its input files; return all problems and the loaded data."""
    result = VerificationResult()

    missing = [
        f"{section}.{key}"
        for section, keys in REQUIRED_KEYS.items()
        for key in keys
        if not isinstance(config.get(section), dict) or key not in config[section]
    ]
    if missing:
        result.errors.append(f"Missing config entries: {', '.join(missing)}.")
        return result

    window = _check_simulation(config["Simulation"], result, now)
    _check_jobs(config["jobs"], result)

    threshold = config["carbon_intensity"]["high_CI_threshold"]
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        result.errors.append(
            f"carbon_intensity.high_CI_threshold must be a number, got {threshold!r}."
        )

    verbosity = config.get("output", {}).get("verbosity")
    if Logging.normalize_verbosity(verbosity) != verbosity:
        result.warnings.append(
            f"Invalid output.verbosity {verbosity!r}, defaulting to 'high'."
        )

    _check_cluster(config["cluster"], config["jobs"], result)
    if window is not None:
        _check_carbon_data(config["carbon_intensity"], window, result)

    return result


def report(result, config_path=None, stream=None):
    """Print warnings and errors; return True if the simulation may start."""
    stream = stream if stream is not None else sys.stderr
    if result.warnings or result.errors:
        where = f" for {config_path}" if config_path is not None else ""
        print(f"Configuration check{where}:", file=stream)
    for message in result.warnings:
        print(f"  WARNING: {message}", file=stream)
    for message in result.errors:
        print(f"  ERROR: {message}", file=stream)
    if result.errors:
        print(
            f"Found {len(result.errors)} error(s); the simulation was not started.",
            file=stream,
        )
    return result.ok


def _check_simulation(section, result, now):
    """Check the Simulation section; return (start, last_update) if the window is valid."""
    valid = True
    raw_start = section["desired_starttime"]
    if raw_start is None:
        # Same rounding as SimulationTime.set_to_current_time().
        start = (now or datetime.now()).replace(second=0, microsecond=0)
    else:
        try:
            start = datetime.strptime(raw_start, START_TIME_FORMAT)
        except (TypeError, ValueError):
            result.errors.append(
                f"Simulation.desired_starttime {raw_start!r} must be 'YYYY-MM-DD HH:MM' or null."
            )
            valid = False

    # A timestep of 0 never advances the clock, so the run would never end.
    for key in ("simulation_length", "timestep"):
        if not _is_count(section[key], 1):
            result.errors.append(
                f"Simulation.{key} must be a positive integer (seconds), got {section[key]!r}."
            )
            valid = False

    # Cluster matches policies by substring, so a typo would silently run as 'none'.
    if section["savings_policy"] not in VALID_SAVINGS_POLICIES:
        result.errors.append(
            f"Simulation.savings_policy {section['savings_policy']!r} is not one of "
            f"{', '.join(VALID_SAVINGS_POLICIES)}."
        )

    if not valid:
        return None
    result.start_time = start.strftime(START_TIME_FORMAT)
    return start, last_update_time(
        start, section["simulation_length"], section["timestep"]
    )


def _check_jobs(section, result):
    for key in ("initial_mix", "regular_incoming_mix"):
        mix = section[key]
        if not isinstance(mix, dict) or not all(
            _is_count(count, 0) for count in mix.values()
        ):
            result.errors.append(
                f"jobs.{key} must map VO names to non-negative integers, got {mix!r}."
            )
    incoming = section.get("incoming_timestep")
    if section["regular_incoming_mix"] and not _is_count(incoming, 1):
        result.errors.append(
            f"jobs.incoming_timestep must be a positive integer (seconds) when "
            f"jobs.regular_incoming_mix is not empty, got {incoming!r}."
        )


def _check_cluster(section, jobs, result):
    try:
        inventory = load_cluster_inventory(
            section["inventory_csv"],
            section["frequency_csv"],
            cluster_name=section["cluster_name"],
            strict=section["strict"],
        )
    except (KeyError, ValueError, OSError, UnicodeDecodeError, csv.Error) as exc:
        result.errors.append(
            f"The cluster files cannot be loaded: {type(exc).__name__}: {exc}"
        )
        return

    if sum(inventory.values()) == 0:
        result.errors.append(
            f"The cluster has no worker nodes: no inventory row of cluster "
            f"{section['cluster_name']!r} with machines and frequency data was loaded."
        )
        return
    result.inventory = inventory

    # A queued job that fits no node blocks the head of the queue for the rest of the run.
    vos = {
        vo
        for key in ("initial_mix", "regular_incoming_mix")
        if isinstance(jobs[key], dict)
        for vo, count in jobs[key].items()
        if count
    }
    for vo in sorted(vos):
        cores, gb_per_core = LARGEST_JOB_BY_VO.get(vo, LARGEST_GENERIC_JOB)
        memory = cores * gb_per_core
        if not any(
            node.node_threads >= cores and node.node_memory_gb >= memory
            for node, quantity in inventory.items()
            if quantity > 0
        ):
            result.errors.append(
                f"Jobs of VO '{vo}' can need {cores} core(s) and {memory} GB, "
                f"but no worker node type has that much."
            )


def _check_carbon_data(section, window, result):
    """Load the rows from the start segment to the first row at or after the last update."""
    path = Path(os.path.join(section["folder"], section["filename"]))
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        result.errors.append(f"The carbon_intensity file cannot be read: {exc}")
        return

    start, last_update = window
    start_segment = SimulationTime.find_hh_segment(start)
    rows = []
    bad_lines = []
    rows_end = None  # Timestamp of the last accepted row.
    for line_number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        fields = line.split(",")
        try:
            timestamp = datetime.strptime(fields[0].strip(), CARBON_TIMESTAMP_FORMAT)
        except ValueError:
            timestamp = None
        if not rows:
            if timestamp != start_segment:
                continue
        elif timestamp is None or timestamp <= rows_end:
            bad_lines.append(f"{line_number} (timestamp not after the previous row)")
            continue
        elif timestamp - rows_end > MAX_CARBON_ROW_SPACING:
            # A gap would silently stretch the previous intensity over the missing time.
            bad_lines.append(f"{line_number} (gap of {timestamp - rows_end})")

        # Columns 1 and 2 are the forecast and the actual intensity in gCO2e/kWh.
        values = [_parse_float(value) for value in fields[1:3]]
        if len(values) < 2 or any(value is None or value < 0 for value in values):
            bad_lines.append(f"{line_number} (missing or invalid intensity)")
        rows.append(fields)
        rows_end = timestamp
        if timestamp >= last_update:
            break

    covered = bool(rows) and rows_end >= last_update
    if not rows:
        result.errors.append(
            f"The carbon_intensity file '{path}' has no row for the start segment "
            f"{start_segment:%Y-%m-%d %H:%M}."
        )
    elif not covered:
        result.errors.append(
            f"The carbon_intensity file '{path}' ends at {rows_end:%Y-%m-%d %H:%M}, but the "
            f"last update of the run is at {last_update:%Y-%m-%d %H:%M}."
        )
    if bad_lines:
        more = f" and {len(bad_lines) - 5} more" if len(bad_lines) > 5 else ""
        result.errors.append(
            f"The carbon_intensity file '{path}' has bad rows inside the simulation window: "
            f"line {', '.join(bad_lines[:5])}{more}."
        )
    if covered and not bad_lines:
        result.carbon_data = rows
