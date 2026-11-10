import pytest

from cluster.ClusterLoader import load_cluster_inventory
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
