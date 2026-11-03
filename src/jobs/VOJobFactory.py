# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY
#                     and the University of Glasgow
# Authors: Dwayne Spiteri and Gordon Stewart.
# For more information about rights and fair use please refer to src/Main.py.
# For full detailed and legal infomration please read the LICENSE and NOTICE
#    files in the main directory
# ===========================================================================

import random

import numpy as np

from jobs.Jobs import Job
from util import Logging

logger = Logging.get_logger()


class VOJobFactory:
    def __init__(self, tag, RAM_per_core=1, cores_req=None):
        self._tag = tag
        self._job_number = 0
        self._memory_required_GB_per_core = RAM_per_core
        self._cores_requested = cores_req

    def __get_duration(self):
        # Calculate duration in minutes, output said duration in seconds.
        # Create the standard here to be empty pilot jobs
        duration_mins = random.gauss(15, 5)  # ~15 mins for an empty pilot to run.
        duration_mins = max(duration_mins, 5)
        return duration_mins * 60

    def __require_cores(self):
        # Determine whether you are running a Single or multicore job.
        if self._cores_requested is None:
            core_num_seed = random.gauss(0, 1)
            if core_num_seed < 0:
                self._cores_requested = 8  # Random 50% chance of requiring 8 or 1 core.
            else:
                self._cores_requested = 1
        return self._cores_requested

    def create_job(self):
        logger.debug("Creating job")
        self._job_number += 1
        name = f"{self._tag}{self._job_number}"
        return Job(
            name,
            self.__get_duration(),
            self._memory_required_GB_per_core,
            self.__require_cores(),
        )


class GridPPJobFactory(VOJobFactory):
    # Test VO to fix all variables associated with jobs.
    def __init__(self, tag, RAM_per_core=2, cores_req=None):
        super().__init__(tag, RAM_per_core, cores_req)

    def __get_duration(self):
        # Calculate duration in minutes, output said duration in seconds.
        durationmins = 300  # Line to test other things work by fixing the lengths of all jobs to 5 hours
        return durationmins * 60

    def __require_cores(self):
        # 100% chance of requring 1 core is nothing is specified.
        if self._cores_requested == None:
            self._cores_requested = 1
        return self._cores_requested

    def create_job(self):
        logger.debug("Creating GridPP production job")
        self._job_number += 1
        name = f"{self._tag}{self._job_number}"
        return Job(
            name,
            self.__get_duration(),
            self._memory_required_GB_per_core,
            self.__require_cores(),
        )


class ATLASJobFactory(VOJobFactory):
    def __init__(self, tag, RAM_per_core=2, cores_req=None):
        super().__init__(tag, RAM_per_core, cores_req)

    def __get_duration(self):
        # Calculate duration in minutes, output said duration in seconds.
        seed = int(600 * random.random())
        if seed < 251:  # empty pilot jobs
            duration_mins = random.gauss(15, 5)  # ~15 mins for an empty pilot to run.
        else:
            duration_mins = random.gauss(
                300, 100
            )  # Average job length is about 5 hours.

        duration_mins = max(duration_mins, 5)
        return duration_mins * 60

    def __require_cores(self):
        # Determine whether you are running a Single or multicore job.
        if self._cores_requested is None:
            core_num_seed = random.randint(0, 101)
            if core_num_seed < 80:
                self._cores_requested = 8  # 80% chance of requiring 8 cores.
            else:
                self._cores_requested = 1  # 20% chance of requiring 1 core.
        return self._cores_requested

    def create_job(self):
        logger.debug("Creating ATLAS production job")
        self._job_number += 1
        name = f"{self._tag}{self._job_number}"
        return Job(
            name,
            self.__get_duration(),
            self._memory_required_GB_per_core,
            self.__require_cores(),
        )


class LHCbJobFactory(VOJobFactory):
    def __init__(self, tag, RAM_per_core=4, cores_req=None):
        super().__init__(tag, RAM_per_core, cores_req)

    def __get_duration(self):
        # Calculate duration in minutes, output said duration in seconds.
        seed = int(100 * random.random())
        if seed < 22:  # empty pilot jobs (21% of the time)
            duration_mins = random.gauss(15, 5)  # ~15 mins for an empty pilot to run.
        else:
            # Creates a function that models the landau distribution of LHCb jobs but with ranges of 9.5 to 19.5.
            job_dist_hours = np.random.choice(
                np.arange(9.5, 19.5, 1),
                p=[
                    1 / 90,
                    2.5 / 90,
                    21 / 90,
                    30 / 90,
                    15 / 90,
                    7.5 / 90,
                    7 / 90,
                    3 / 90,
                    2 / 90,
                    1 / 90,
                ],
            )  # Average job length is about 12 hours.
            duration_mins = 60 * job_dist_hours

        duration_mins = max(duration_mins, 5)
        return duration_mins * 60

    def __require_cores(self):
        # Determine whether you are running a Single or multicore job.
        if self._cores_requested is None:
            core_num_seed = random.randint(0, 101)
            if core_num_seed < 10:
                self._cores_requested = 8  # 10% chance of requiring 8 cores.
            else:
                self._cores_requested = 1  # 90% chance of requiring 1 core.
        return self._cores_requested

    def create_job(self):
        logger.debug("Creating LHCb production job")
        self._job_number += 1
        name = f"{self._tag}{self._job_number}"
        return Job(
            name,
            self.__get_duration(),
            self._memory_required_GB_per_core,
            self.__require_cores(),
        )
