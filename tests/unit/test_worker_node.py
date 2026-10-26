from cluster.WorkerNode import WorkerNode
from jobs.Jobs import Job
from simulation.Time import SimulationTime


def _make_node(threads=8, memory=8):
    simulation_time = SimulationTime({"output": {"verbosity": "low"}}, "2024-01-16 16:00")
    node = WorkerNode(
        simulation_time,
        "test-node",
        threads=threads,
        memory=memory,
        idlepower=50,
        freq_dep_specs={3.0: (200, 1939.60)},
    )
    node.set_datalogger_handlers(lambda job, worker_node: None, lambda job, worker_node: None)
    return node


def test_multicore_job_memory_is_checked_against_total_footprint():
    # memory_req is GB per core: an 8-core job at 2 GB/core needs 16 GB and
    # must not be admitted onto a node with only 8 GB.
    node = _make_node(memory=8)
    job = Job("multicore", 18000, memory_req=2, cores_req=8)

    assert node.can_schedule_job(job) is False


def test_multicore_job_fits_when_total_memory_is_available():
    node = _make_node(memory=16)
    job = Job("multicore", 18000, memory_req=2, cores_req=8)

    assert node.can_schedule_job(job) is True

    node.start_job(job)

    assert node.busy_RAM == 16
    assert node.get_memory_available() == 0
