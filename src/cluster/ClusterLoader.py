# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY
#                     and the University of Glasgow
# For more information about rights and fair use please refer to src/Main.py.
# For full detailed and legal information please read the LICENSE and NOTICE
#    files in the main directory
# ===========================================================================

"""Runtime loader for cluster node definitions.

This module replaces generated hardcoded node subclasses with dynamic loading
from CSV inputs at startup.
"""

from __future__ import annotations

import csv
from pathlib import Path

from cluster.WorkerNode import WorkerNode
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


def load_cluster_inventory(
    machinegroups_inventory_csv: str | Path,
    frequency_dependence_csv: str | Path,
    cluster_name: str | None = None,
    strict: bool = True,
) -> tuple[dict[str, int], list[WorkerNode]]:
    """Load the cluster inventory and initialize `WorkerNode` objects.

    Parameters
    ----------
    machinegroups_inventory_csv: str | Path
        Path to the machine inventory CSV.
    frequency_dependence_csv: str | Path
        Path to the frequency dependence CSV.
    cluster_name: str | None, optional
        From the ``cluster(main_Puppet_hostgroup)`` column.
    strict: bool, optional
        If True, raise error on malformed or missing data.
        If False, log a warning and skip the entry. Defaults to True.

    Returns
    ----------
    tuple: A tuple containing:
        - An `inventory` dictionary mapping each node key to its quantity.
        - A list of `WorkerNode` objects instantiated based on the data in that dictionary.
    """

    machinegroups_inventory_csv = _resolve_path(machinegroups_inventory_csv)
    frequency_dependence_csv = _resolve_path(frequency_dependence_csv)

    frequencies_by_node = _load_frequency_map(frequency_dependence_csv, strict=strict)
    inventory = {}
    worker_nodes = []

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

            inventory[node_key] = quantity
            for node_number in range(quantity):
                # Adds the quantity of nodes specified in the Simulation.
                worker_nodes.append(
                    WorkerNode(
                        node_key,
                        node_number,
                        threads,
                        memory_gb,
                        idle_power_w,
                        freq_dep_specs,
                        row.get("model", "").strip(),
                        row.get("cpu_model", "").strip(),
                        int(row.get("installation_date", "").strip()),
                    )
                )

    logger.info(
        "Loaded %d worker node types from %s and %s",
        len(inventory),
        machinegroups_inventory_csv,
        frequency_dependence_csv,
    )
    return inventory, worker_nodes
