# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY
#                     and the University of Glasgow
# For more information about rights and fair use please refer to src/Main.py.
# For full detailed and legal information please read the LICENSE and NOTICE
#    files in the main directory
# ===========================================================================

from datetime import datetime, timedelta

from util import Logging

logger = Logging.get_logger()


class SimulationTime:
    def __init__(self, config_or_time, time=None):
        self._time = None
        self._start_time = None
        self._timestep_seconds = 600

        # Backward compatible signatures:
        # - SimulationTime(config, time)
        # - SimulationTime(time_string)
        if not isinstance(config_or_time, dict):
            time = config_or_time if time is None else time

        if time is None:
            self.set_to_current_time()
        else:
            self.set_to_time(datetime.strptime(time, "%Y-%m-%d %H:%M"))

        self._start_time = self._time

        self._origin = datetime.now()

        logger.debug("Set origin: %s", self._origin)

    def set_to_current_time(self):
        stringtime = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.set_to_time(
            datetime.strptime(stringtime, "%Y-%m-%d %H:%M")
        )  # Since you can't seem to directly format a datetime

    def set_to_time(self, time):
        self._time = time
        logger.debug("Set to time: %s", self._time)

    @staticmethod
    def find_hh_segment(dt, instruction="current"):
        nudge = (
            dt + timedelta(seconds=1)
        )  # If we start on the half-hour it counts as starting on the previous, so nudge it forward
        delta = timedelta(minutes=30)
        next_hh_seg = (
            nudge + (datetime.min - nudge) % delta
        )  # finds the half hour segment after a time given in the right format
        if instruction == "next":
            return next_hh_seg
        else:
            return next_hh_seg - delta

    def advance(self):
        self._time += timedelta(seconds=self._timestep_seconds)
        logger.debug("Current time: %s", self._time)

    def get_start_datetime(self):  # Get the start datetime input into the simulation
        return self._start_time

    def get_origin_datetime(self):  # Get the real time that the simulation was started.
        return self._origin

    def get_current_datetime(self):
        return self._time

    def get_timestep(self):
        return self._timestep_seconds
