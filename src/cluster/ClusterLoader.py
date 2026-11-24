# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY
#                     and the University of Glasgow
# For more information about rights and fair use please refer to src/Main.py.
# For full detailed and legal information please read the LICENSE and NOTICE
#    files in the main directory
# ===========================================================================

"""Runtime loader for cluster node definitions.

The cluster is read either from a machine-group inventory CSV with a frequency
dependence CSV, or from a directory with one inventory JSON file per machine.
"""

from __future__ import annotations

import csv
import json
from datetime import date
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


def _read_node_json(path: Path) -> WorkerNode:
    """Build one `WorkerNode` from a per-machine inventory JSON; raise ValueError if incomplete."""
    node = json.loads(path.read_text(encoding="utf-8"))
    try:
        hostname = node["node_id"].strip()
        threads = int(node["number_of_vcores"])
        memory_gb = sum(
            float(ram["number_of_modules"]) * float(ram["storage_per_module_gb"])
            for ram in node["ramList"]
        )
        idle_power_w = float(node["power_consumption"]["idle"])
        dependence = node["power_consumption"]["cpu_frequency_dependence"]
        frequencies_mhz = [float(f) for f in dependence["cpu_frequency_Mhz"]]
        powers_w = [float(p) for p in dependence["power_W"]]
        hep_scores = [float(h) for h in dependence["hepscore"]]
        cpu_model = node["cpu"]["model"].strip()
        installation_date = node["installation_date"]
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ValueError(f"Incomplete or invalid node data in {path}: {exc!r}") from exc
    try:
        year = date.fromisoformat(installation_date).year
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid installation_date {installation_date!r} in {path}, "
            f"expected YYYY-MM-DD"
        ) from exc

    problems = []
    if not hostname:
        problems.append("empty node_id")
    if threads < 1:
        problems.append(f"number_of_vcores = {threads}")
    if node["cpu"].get("vcores_per_machine", threads) != threads:
        problems.append(
            f"number_of_vcores = {threads} but cpu.vcores_per_machine = "
            f"{node['cpu']['vcores_per_machine']}"
        )
    if memory_gb <= 0:
        problems.append("no memory in ramList")
    if idle_power_w <= 0:
        problems.append(f"power_consumption.idle = {idle_power_w}")
    if not frequencies_mhz:
        problems.append("no cpu_frequency_dependence points")
    if not len(frequencies_mhz) == len(powers_w) == len(hep_scores):
        problems.append(
            f"cpu_frequency_dependence lists differ in length "
            f"({len(frequencies_mhz)} frequencies, {len(powers_w)} powers, "
            f"{len(hep_scores)} hepscores)"
        )
    if problems:
        raise ValueError(f"Incomplete node data in {path}: {'; '.join(problems)}")

    freq_dep_specs = {
        f / 1000.0: (p, h) for f, p, h in zip(frequencies_mhz, powers_w, hep_scores)
    }
    return WorkerNode(
        hostname,
        0,
        threads,
        memory_gb,
        idle_power_w,
        freq_dep_specs,
        "",
        cpu_model,
        year,
        hostname=hostname,
    )


def load_cluster_directory(
    inventory_dir: str | Path,
    pattern: str = "*",
    group: str | None = None,
    strict: bool = True,
) -> tuple[dict[str, int], list[WorkerNode]]:
    """Load the cluster from a directory with one inventory JSON file per machine.

    Parameters
    ----------
    inventory_dir: str | Path
        Directory with the per-machine JSON files.
    pattern: str, optional
        Glob pattern of the node files in that directory. Defaults to ``"*"``.
        Matching files that are not JSON objects are skipped with a warning.
    group: str | None, optional
        Keep only machines whose ``group`` field equals this; ``None`` keeps all.
    strict: bool, optional
        If True, raise an error on incomplete or invalid node data.
        If False, log a warning and skip the machine. Defaults to True.

    Returns
    ----------
    tuple: A tuple containing:
        - An `inventory` dictionary mapping each hostname to 1.
        - One `WorkerNode` per machine, in file-name order.
    """
    inventory_dir = _resolve_path(inventory_dir)
    if not inventory_dir.is_dir():
        raise FileNotFoundError(f"Inventory directory {inventory_dir} does not exist")

    inventory = {}
    worker_nodes = []
    for path in sorted(p for p in inventory_dir.glob(pattern) if p.is_file()):
        try:
            node = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            node = None
        if not isinstance(node, dict):
            logger.warning("Skipping %s: not a JSON node file", path)
            continue
        if group is not None and node.get("group", "") != group:
            continue

        try:
            worker_node = _read_node_json(path)
        except ValueError as exc:
            if strict:
                raise
            logger.warning("Skipping machine: %s", exc)
            continue
        if worker_node.hostname in inventory:
            message = f"Duplicate node_id {worker_node.hostname!r} in {path}"
            if strict:
                raise ValueError(message)
            logger.warning("Skipping machine: %s", message)
            continue

        inventory[worker_node.hostname] = 1
        worker_nodes.append(worker_node)

    logger.info("Loaded %d worker nodes from %s", len(worker_nodes), inventory_dir)
    return inventory, worker_nodes
