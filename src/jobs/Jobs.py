# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY
#                     and the University of Glasgow
# Authors: Dwayne Spiteri and Gordon Stewart.
# For more information about rights and fair use please refer to src/Main.py.
# For full detailed and legal infomration please read the LICENSE and NOTICE
#    files in the main directory
# ===========================================================================

import datetime


class Job:
    def __init__(self, name, duration, memory_req=1, cores_req=1):
        self.name = name
        self._duration = duration
        self.memory_req = memory_req  # In GB-per-core.
        self.cores_req = cores_req
        self._start_time = None
        self._end_time = None

    def __str__(self):
        return self.name

    # -----------------
    # Getters
    # -----------------
    @property
    def duration(self):
        return self._duration

    @property
    def start_time(self):
        return self._start_time

    @property
    def end_time(self):
        return self._end_time

    # -----------------
    # Setters
    # -----------------
    @duration.setter
    def duration(self, value):
        self._duration = value
        if self._start_time is not None:
            self._end_time = self._start_time + datetime.timedelta(
                seconds=self.duration
            )

    @start_time.setter
    def start_time(self, value):
        self._start_time = value
        self._end_time = self._start_time + datetime.timedelta(seconds=self.duration)

    @end_time.setter  # For if you conduct a process that changes the life of a job while it is in progress.
    def end_time(self, value):
        self._end_time = value
