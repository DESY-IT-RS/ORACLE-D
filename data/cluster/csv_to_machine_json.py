# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY
#                     and the University of Glasgow

"""Write one inventory JSON file per machine from an inventory CSV and a frequency CSV.

The files hold only the fields of the SUSFECIT inventory template that the simulation
reads with ``cluster.inventory_dir``. Machines get the hostnames the CSV loader gives them (``<type>_<subtype>-NNN``)
and the files are numbered in CSV order, so both loaders build the nodes in the same order.

    python3 data/cluster/csv_to_machine_json.py \\
        data/cluster/default-machinegroups_inventory.csv \\
        data/cluster/default-frequency_dependence.csv data/cluster/default-machines
"""

import argparse
import csv
import json
from pathlib import Path


def machine_node(node_id, group, threads, memory_gb, idle_w, points, cpu_model, year):
    """One machine; points are (MHz, W, HEPScore) tuples. Memory is one module of memory_gb."""
    return {
        "node_id": node_id,
        "group": group,
        "installation_date": f"{year}-01-01",
        "number_of_vcores": threads,
        "power_consumption": {
            "idle": idle_w,
            "cpu_frequency_dependence": {
                "cpu_frequency_Mhz": [p[0] for p in points],
                "hepscore": [p[2] for p in points],
                "power_W": [p[1] for p in points],
            },
        },
        "cpu": {"model": cpu_model},
        "ramList": [{"number_of_modules": 1, "storage_per_module_gb": memory_gb}],
    }


def _number(raw):
    value = float(raw)
    return int(value) if value.is_integer() else value


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("inventory_csv", type=Path)
    parser.add_argument("frequency_csv", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--prefix", default="inv_", help="file name prefix (default inv_)")
    args = parser.parse_args()

    points_by_key = {}
    with args.frequency_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            points_by_key[f"{row[1].strip()}_{row[2].strip()}"] = [
                tuple(_number(x) for x in entry.split("_"))
                for entry in row[4:]
                if entry.strip()
            ]

    with args.inventory_csv.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    total = sum(int(float(row["number_machines"])) for row in rows)
    width = len(str(total - 1))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    index = 0
    for row in rows:
        key = f"{row['type'].strip()}_{row['subtype'].strip()}"
        for number in range(int(float(row["number_machines"]))):
            hostname = f"{key}-{number + 1:03}"
            node = machine_node(
                hostname,
                row["cluster(main_Puppet_hostgroup)"].strip(),
                int(float(row["total_threads"])),
                _number(row["total_mem_in_Gb"]),
                float(row["power_min_60d"]),
                points_by_key[key],
                row["cpu_model"].strip(),
                int(row["installation_date"]),
            )
            path = args.out_dir / f"{args.prefix}{index:0{width}}.{hostname}"
            path.write_text(json.dumps(node, indent=2) + "\n")
            index += 1
    print(f"Wrote {index} machine files to {args.out_dir}")


if __name__ == "__main__":
    main()
