import json
from pathlib import Path

import pytest

from cluster.ClusterLoader import load_cluster_directory, load_cluster_inventory
from cluster.WorkerNode import WorkerNode

FREQUENCY_HEADER = "hostname,type,subtype,latest measurement,frequency_power_hepscore\n"
INVENTORY_HEADER = (
    "representative,timestamp_check,number_machines,number_decommissioned,type,subtype,"
    "comment,manufacturer,model,cpu_model,hepscore,installation_date,"
    "cluster(main_Puppet_hostgroup),total_cores,total_threads,total_mem_in_Gb,"
    "power_min_60d,power_max_60d\n"
)


def test_load_cluster_inventory_from_minimal_csvs(fixture_paths):
    inventory, worker_nodes = load_cluster_inventory(
        fixture_paths.inventory_csv,
        fixture_paths.frequency_csv,
        cluster_name="TEST",
        strict=True,
    )

    assert len(inventory) == 1

    node_type, quantity = next(iter(inventory.items()))
    assert node_type == "TESTNODE_0"
    assert quantity == 1

    assert len(worker_nodes) == 1
    worker_node = worker_nodes[0]

    assert isinstance(worker_node, WorkerNode)
    assert worker_node.hostname == "TESTNODE_0-001"
    assert worker_node.number_of_cores == 2
    assert worker_node.max_RAM == 8.0
    assert worker_node.powerusage_idle == 50.0 / 3600
    assert worker_node.frequencies_available == [3.0]
    assert worker_node.HEPScore_vs_frequency == [1939.60]


def test_load_cluster_inventory_respects_cluster_filter(fixture_paths):
    inventory, worker_nodes = load_cluster_inventory(
        fixture_paths.inventory_csv,
        fixture_paths.frequency_csv,
        cluster_name="OTHER",
        strict=True,
    )

    assert inventory == {}
    assert worker_nodes == []


def test_load_cluster_inventory_strict_raises_on_malformed_frequency_entry(
    tmp_path, fixture_paths
):
    frequency_csv = tmp_path / "frequency.csv"
    frequency_csv.write_text(
        FREQUENCY_HEADER + "test-node,TESTNODE,0,2024-01-01T00:00:00,3000_200\n"
    )

    with pytest.raises(ValueError):
        load_cluster_inventory(
            fixture_paths.inventory_csv, frequency_csv, cluster_name="TEST", strict=True
        )


def test_load_cluster_inventory_lenient_skips_malformed_frequency_entry(
    tmp_path, fixture_paths
):
    frequency_csv = tmp_path / "frequency.csv"
    frequency_csv.write_text(
        FREQUENCY_HEADER
        + "test-node,TESTNODE,0,2024-01-01T00:00:00,3000_200,3000_200_1939.60\n"
    )

    inventory, worker_nodes = load_cluster_inventory(
        fixture_paths.inventory_csv, frequency_csv, cluster_name="TEST", strict=False
    )

    assert len(inventory) == 1

    worker_node = worker_nodes[0]

    assert worker_node.frequencies_available == [3.0]
    assert worker_node.HEPScore_vs_frequency == [1939.60]


def test_load_cluster_inventory_strict_raises_on_missing_frequency_data(
    tmp_path, fixture_paths
):
    frequency_csv = tmp_path / "frequency.csv"
    frequency_csv.write_text(
        FREQUENCY_HEADER
        + "other-node,OTHERNODE,0,2024-01-01T00:00:00,3000_200_1939.60\n"
    )

    with pytest.raises(KeyError):
        load_cluster_inventory(
            fixture_paths.inventory_csv, frequency_csv, cluster_name="TEST", strict=True
        )


def test_load_cluster_inventory_lenient_skips_node_without_frequency_data(
    tmp_path, fixture_paths
):
    frequency_csv = tmp_path / "frequency.csv"
    frequency_csv.write_text(
        FREQUENCY_HEADER
        + "other-node,OTHERNODE,0,2024-01-01T00:00:00,3000_200_1939.60\n"
    )

    inventory, worker_nodes = load_cluster_inventory(
        fixture_paths.inventory_csv, frequency_csv, cluster_name="TEST", strict=False
    )

    assert inventory == {}
    assert worker_nodes == []


def test_load_cluster_inventory_strict_raises_on_invalid_numeric_inventory_value(
    tmp_path, fixture_paths
):
    inventory_csv = tmp_path / "inventory.csv"
    inventory_csv.write_text(
        INVENTORY_HEADER
        + "test-node,2024-01-01T00:00:00,not-a-number,0,TESTNODE,0,,,Test Model,Test CPU,"
        "1939.60,2024,TEST,1,2,8,50,200\n"
    )

    with pytest.raises(ValueError):
        load_cluster_inventory(
            inventory_csv, fixture_paths.frequency_csv, cluster_name="TEST", strict=True
        )


def test_load_cluster_inventory_lenient_skips_invalid_numeric_inventory_value(
    tmp_path, fixture_paths
):
    inventory_csv = tmp_path / "inventory.csv"
    inventory_csv.write_text(
        INVENTORY_HEADER
        + "test-node,2024-01-01T00:00:00,not-a-number,0,TESTNODE,0,,,Test Model,Test CPU,"
        "1939.60,2024,TEST,1,2,8,50,200\n"
    )

    inventory, worker_nodes = load_cluster_inventory(
        inventory_csv, fixture_paths.frequency_csv, cluster_name="TEST", strict=False
    )

    assert inventory == {}
    assert worker_nodes == []


# ---------------------------------------------------------------------------
#   One inventory JSON file per machine
# ---------------------------------------------------------------------------


def _copy_nodes(fixture_paths, tmp_path, edit=None):
    """Copy the node fixtures to tmp_path, applying edit(name, node) to each JSON node."""
    for path in fixture_paths.node_dir.iterdir():
        text = path.read_text()
        if path.name.startswith("inv_"):
            node = json.loads(text)
            if edit is not None:
                edit(path.name, node)
            text = json.dumps(node)
        (tmp_path / path.name).write_text(text)
    return tmp_path


def test_load_cluster_directory_builds_one_node_per_machine_file(fixture_paths, caplog):
    inventory, worker_nodes = load_cluster_directory(fixture_paths.node_dir, strict=True)

    assert inventory == {"node-a.test": 1, "node-b.test": 1}
    assert [node.hostname for node in worker_nodes] == ["node-a.test", "node-b.test"]
    assert "clush_command" in caplog.text

    node_a, node_b = worker_nodes
    assert node_a.number_of_cores == 2
    assert node_a.max_RAM == 8.0
    assert node_a.powerusage_idle == 50.0 / 3600
    assert node_a.frequencies_available == [3.0]
    assert node_a.HEPScore_vs_frequency == [1939.60]
    assert node_a.cpu_model == "Test CPU"
    assert node_a.year == 2024

    assert node_b.number_of_cores == 4
    assert node_b.max_RAM == 16.0
    assert node_b.frequencies_available == [3.0, 2.0]
    assert node_b.HEPScore_vs_frequency == [2000.0, 1500.0]
    assert node_b.year == 2022


def test_load_cluster_directory_filters_on_group_and_pattern(fixture_paths):
    inventory, _ = load_cluster_directory(fixture_paths.node_dir, group="OTHER")
    assert inventory == {"node-b.test": 1}

    inventory, _ = load_cluster_directory(fixture_paths.node_dir, pattern="*node-a*")
    assert inventory == {"node-a.test": 1}


@pytest.mark.parametrize(
    "edit, message",
    [
        (lambda n: n["power_consumption"].update(idle=0.0), "power_consumption.idle"),
        (
            lambda n: n["power_consumption"]["cpu_frequency_dependence"].update(
                cpu_frequency_Mhz=[], power_W=[], hepscore=[]
            ),
            "no cpu_frequency_dependence points",
        ),
        (
            lambda n: n["power_consumption"]["cpu_frequency_dependence"].update(
                hepscore=[]
            ),
            "differ in length",
        ),
        (lambda n: n["cpu"].update(vcores_per_machine=8), "vcores_per_machine"),
        (lambda n: n.update(installation_date="2024"), "installation_date"),
        (lambda n: n.pop("ramList"), "ramList"),
    ],
)
def test_load_cluster_directory_incomplete_node(fixture_paths, tmp_path, edit, message):
    def edit_node_b(name, node):
        if "node-b" in name:
            edit(node)

    node_dir = _copy_nodes(fixture_paths, tmp_path, edit_node_b)

    with pytest.raises(ValueError, match=message):
        load_cluster_directory(node_dir, strict=True)

    inventory, _ = load_cluster_directory(node_dir, strict=False)
    assert inventory == {"node-a.test": 1}


def test_load_cluster_directory_duplicate_node_id(fixture_paths, tmp_path):
    node_dir = _copy_nodes(
        fixture_paths, tmp_path, lambda name, node: node.update(node_id="same.test")
    )

    with pytest.raises(ValueError, match="Duplicate node_id 'same.test'"):
        load_cluster_directory(node_dir, strict=True)

    inventory, _ = load_cluster_directory(node_dir, strict=False)
    assert inventory == {"same.test": 1}


def test_load_cluster_directory_missing_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_cluster_directory(tmp_path / "missing")


def test_shipped_default_machine_files_match_the_default_csvs():
    data_dir = Path(__file__).resolve().parents[2] / "data" / "cluster"
    _, csv_nodes = load_cluster_inventory(
        data_dir / "default-machinegroups_inventory.csv",
        data_dir / "default-frequency_dependence.csv",
        cluster_name="DEFAULT",
    )
    _, json_nodes = load_cluster_directory(data_dir / "default-machines", group="DEFAULT")

    def describe(node):
        return (
            node.hostname,
            node.number_of_cores,
            node.max_RAM,
            node.powerusage_idle,
            node.frequencies_available,
            node.powers_available,
            node.HEPScore_vs_frequency,
            node.cpu_model,
            node.year,
        )

    assert len(json_nodes) == 310
    assert [describe(n) for n in json_nodes] == [describe(n) for n in csv_nodes]
