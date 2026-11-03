# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY
#                     and the University of Glasgow
# Authors: Dwayne Spiteri and Gordon Stewart.

"""Runtime loader for cluster node definitions.

This module replaces generated hardcoded node subclasses with dynamic loading
from CSV inputs at startup.
"""

from __future__ import annotations

import csv
from pathlib import Path

from util import Logging

logger = Logging.get_logger()


def _resolve_path(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = Path.cwd() / resolved
    return resolved


def _load_frequency_map(frequency_csv: Path, strict: bool = True):
    """Load per-node frequency dependence map from CSV."""
    frequencies_by_node = {}

    with frequency_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        _ = next(reader, None)

        for row in reader:
            if len(row) < 5:
                continue

            node_type = row[1].strip()
            node_subtype = row[2].strip()
            node_key = f"{node_type}_{node_subtype}"

            specs = {}
            for raw_entry in row[4:]:
                raw_entry = raw_entry.strip()
                if not raw_entry:
                    continue

                parts = raw_entry.split("_")
                if len(parts) != 3:
                    if strict:
                        raise ValueError(
                            f"Malformed frequency entry '{raw_entry}' for node {node_key} "
                            f"in {frequency_csv}"
                        )
                    logger.warning(
                        f"Skipping malformed frequency entry '{raw_entry}' for node {node_key}"
                    )
                    continue

                freq_mhz, power_w, hep_score = parts
                specs[float(freq_mhz) / 1000.0] = (float(power_w), float(hep_score))

            if not specs:
                if strict:
                    raise ValueError(
                        f"No frequency points found for node {node_key} in {frequency_csv}"
                    )
                logger.warning(f"Skipping node {node_key} with no frequency points")
                continue

            frequencies_by_node[node_key] = specs

    return frequencies_by_node


def _build_worker_node_class(
    base_worker_node_class,
    *,
    node_key: str,
    threads: int,
    memory_gb: float,
    idle_power_w: float,
    freq_dep_specs: dict[float, tuple[float, float]],
    system: str,
    cpu_model: str,
    install_year: str,
):
    """Create a WorkerNode subclass at runtime for one node type."""

    class_name = f"WorkerNode_{node_key}"

    def __init__(self, simulation_time, hostname=""):
        base_worker_node_class.__init__(
            self,
            simulation_time,
            f"{node_key}{hostname}",
            threads,
            memory_gb,
            idle_power_w,
            freq_dep_specs,
        )
        self._system = system
        self._cpu = cpu_model
        self._year = install_year

    new_class = type(class_name, (base_worker_node_class,), {"__init__": __init__})
    new_class.__module__ = __name__
    return new_class


def load_cluster_inventory(
    machinegroups_inventory_csv: str | Path,
    frequency_dependence_csv: str | Path,
    *,
    base_worker_node_class=None,
    cluster_name: str | None = None,
    strict: bool = True,
):
    """Load cluster inventory as a mapping {WorkerNodeSubclass: quantity}.

    Args:
        machinegroups_inventory_csv: Path to machine inventory CSV.
        frequency_dependence_csv: Path to frequency dependence CSV.
        base_worker_node_class: Base WorkerNode class to subclass. If None,
            imported from ``cluster.WorkerNodes_DESY_GRID`` for compatibility.
        cluster_name: Optional filter on ``cluster(main_Puppet_hostgroup)``.
        strict: If True, raise on malformed/missing data. If False, log and skip.
    """
    if base_worker_node_class is None:
        # Backward-compatible default while base class still lives there.
        from cluster.WorkerNode import WorkerNode

        base_worker_node_class = WorkerNode

    machinegroups_inventory_csv = _resolve_path(machinegroups_inventory_csv)
    frequency_dependence_csv = _resolve_path(frequency_dependence_csv)

    frequencies_by_node = _load_frequency_map(frequency_dependence_csv, strict=strict)
    inventory = {}

    with machinegroups_inventory_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_cluster_name = row.get("cluster(main_Puppet_hostgroup)", "").strip()
            if cluster_name is not None and row_cluster_name != cluster_name:
                continue

            node_type = row["type"].strip()
            node_subtype = row["subtype"].strip()
            node_key = f"{node_type}_{node_subtype}"

            freq_dep_specs = frequencies_by_node.get(node_key)
            if freq_dep_specs is None:
                message = (
                    f"No frequency dependence data for node type {node_key}; "
                    f"row representative={row.get('representative', '')} skipped"
                )
                if strict:
                    raise KeyError(message)
                logger.warning(message)
                continue

            try:
                quantity = int(float(row["number_machines"]))
                threads = int(float(row["total_threads"]))
                memory_gb = float(row["total_mem_in_Gb"])
                idle_power_w = float(row["power_min_60d"])
            except (TypeError, ValueError) as exc:
                message = (
                    f"Invalid numeric value in inventory row for {node_key}: {exc}"
                )
                if strict:
                    raise ValueError(message) from exc
                logger.warning(message)
                continue

            worker_node_class = _build_worker_node_class(
                base_worker_node_class,
                node_key=node_key,
                threads=threads,
                memory_gb=memory_gb,
                idle_power_w=idle_power_w,
                freq_dep_specs=freq_dep_specs,
                system=row.get("model", "").strip(),
                cpu_model=row.get("cpu_model", "").strip(),
                install_year=row.get("installation_date", "").strip(),
            )
            inventory[worker_node_class] = quantity

    logger.info(
        "Loaded %d worker node types from %s and %s",
        len(inventory),
        machinegroups_inventory_csv,
        frequency_dependence_csv,
    )
    return inventory
