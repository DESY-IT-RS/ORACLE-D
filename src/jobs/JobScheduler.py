# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY
#                     and the University of Glasgow
# Authors: Dwayne Spiteri and Gordon Stewart.
# For more information about rights and fair use please refer to src/Main.py.
# For full detailed and legal infomration please read the LICENSE and NOTICE
#    files in the main directory
# ===========================================================================

from jobs.VOJobFactory import (
    ATLASJobFactory,
    GridPPJobFactory,
    LHCbJobFactory,
    VOJobFactory,
)


class JobScheduler:
    def __init__(
        self,
        simulation_time,
        cluster_to_submit_jobs_to,
        inital_job_mix=None,
        regular_incoming_jobs=None,
    ):
        self._simulation_time = simulation_time
        self._cluster = cluster_to_submit_jobs_to

        # Load in the job mixed
        self._inital_job_mix = inital_job_mix
        self._regular_incoming_jobs = regular_incoming_jobs

        # Create the job factories
        self._basic_job = VOJobFactory("VO-Basic-")
        self._gridpp_job = GridPPJobFactory("GridPP-")
        self._atlas_prod = ATLASJobFactory("ATLAS-Prod-")
        self._lhcb_prod = LHCbJobFactory("LHCb-Prod-")

        self._gridpp_hourly = GridPPJobFactory("GridPP-Hourly")
        self._atlas_hourly = ATLASJobFactory("ATLAS-Hourly-")
        self._lhcb_hourly = LHCbJobFactory("LHCb-Hourly-")

        # Seed the cluster with initial jobs
        # Format for initial jobs is a dictionary of {'VO1':jobs, 'VO2':jobs, [...]}
        if self._inital_job_mix is not None:
            for VO, amount in self._inital_job_mix.items():
                if VO == "ATLAS":
                    for _ in range(amount):
                        self._cluster.submit_job(self._atlas_prod.create_job())
                elif VO == "LHCb":
                    for _ in range(amount):
                        self._cluster.submit_job(self._lhcb_prod.create_job())
                elif VO == "GridPP":
                    for _ in range(amount):
                        self._cluster.submit_job(self._gridpp_job.create_job())
                else:
                    for _ in range(amount):
                        self._cluster.submit_job(self._basic_job.create_job())

    def update(self):
        # Jobs to be submitted while the simulation is ongoing
        # Format for regular jobs is a tuple of a dictionary of [{'VO1':jobs per X seconds, 'VO2':jobs per X seconds, [...]}, X]
        if self._regular_incoming_jobs is not None:
            for job_list in self._regular_incoming_jobs:
                if len(job_list) != 2:
                    raise TypeError(
                        "The type of jobs in this list of lists should be a tuple of [ {VO : jobs_per_cycle}, cycle_in_sec ]"
                    )

                dict_VO_jobs_per_cycle = job_list[0]
                cycle = job_list[1]
                # Check to see if multiples of cycle number of seconds have gone by.
                timediff = (
                    self._simulation_time.get_current_datetime()
                    - self._simulation_time.get_start_datetime()
                )
                cycles_passed = timediff.total_seconds() / cycle

                if (
                    not self._cluster.has_running_jobs()
                    and not self._cluster.has_queued_jobs()
                ):
                    continue

                if cycles_passed != 0 and cycles_passed % 1 == 0:
                    for VO, amount in dict_VO_jobs_per_cycle.items():
                        if VO == "ATLAS":
                            for _ in range(amount):
                                self._cluster.submit_job(
                                    self._atlas_hourly.create_job()
                                )
                        elif VO == "LHCb":
                            for _ in range(amount):
                                self._cluster.submit_job(self._lhcb_hourly.create_job())
                        elif VO == "GridPP":
                            for _ in range(amount):
                                self._cluster.submit_job(
                                    self._gridpp_hourly.create_job()
                                )
                        else:
                            for _ in range(amount):
                                self._cluster.submit_job(self._basic_job.create_job())
