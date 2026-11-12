# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY
#                     and the University of Glasgow
# Authors: Dwayne Spiteri and Gordon Stewart.
# For more information about rights and fair use please refer to src/Main.py.
# For full detailed and legal infomration please read the LICENSE and NOTICE
#    files in the main directory
# ===========================================================================
from collections import deque
from datetime import datetime, timedelta
from typing import Any

from cluster.WorkerNode import *
from jobs.Jobs import Job
from util import Logging

logger = Logging.get_logger()


class Cluster:
    def __init__(
        self,
        config: dict,
        simulation_time: "SimulationTime",
        worker_node_inventory: dict[str, int],
        worker_nodes: list[WorkerNode],
        carbon_intensity_data: list[Any],
        es_gimmick: str,
        carbon_intensity_threshold: int = 200,
    ):
        """Creates the cluster to be simulated.

        Parameters
        ----------
        config : dict
            The configuration of the cluster.
        simulation_time : SimulationTime
            The global simulation time.
        worker_node_inventory : dict[WorkerNode,int]
            Maps each WorkerNode template to the quantity of nodes to create,
            e.g. ``{WorkerNode_d20: 40, WorkerNode_d21: 32, WorkerNode_d22: 36}``.
        carbon_intensity_data : list
            Contains the carbon intensity data.
        es_gimmick : str
            Name of the experiment to run on the cluster.
        carbon_intensity_threshold : int, optional
            Carbon intensity threshold, in gCO2/kWh, above which the
            energy-saving attempt is triggered. Defaults to ``200``.
        """

        self._simulation_time = simulation_time
        self._worker_node_inventory = worker_node_inventory
        self._worker_nodes = worker_nodes
        for worker_node in self._worker_nodes:
            worker_node.simulation_time = simulation_time
        self._queued_jobs = deque[Job]()
        self._timestep_power_dissipated = 0
        self._timestep_carbon_consumed = 0
        self._timestep_occupancy = 0
        self._days = 0
        self._last_day = ""

        self._job_submitted_handler = None
        self._energy_and_carbon_consumed_handler = None
        self._peaktime_energy_and_carbon_consumed_handler = None
        self._occupancy_handler = None

        self._carbondata = carbon_intensity_data
        self._energy_saving_try = es_gimmick
        self._cditerant = 0  # Create an iterant that marks place in the carbon data list w.r.t simulation time to be incrimented w.r.t the timestep of the simulation.
        self._CIThresholdValue = carbon_intensity_threshold
        self._in_clkdown = (
            False  # Flags to make decisions based on the status of the cluster.
        )
        self._anticipate_clkdown = False
        self._anticipate_clockup = False

        self._mission_accomplished = False  # State of completion for the simulation.

        logger.info(
            "Created cluster with %d worker nodes and %d cores",
            self.get_number_of_nodes(),
            self.get_number_of_cores(),
        )

    def set_datalogger_handlers(
        self,
        job_submitted,
        job_started,
        job_finished,
        energy_and_carbon_consumed,
        peaktime_energy_and_carbon_consumed,
        occupancy,
    ):
        self._job_submitted_handler = job_submitted
        self._energy_and_carbon_consumed_handler = energy_and_carbon_consumed
        self._peaktime_energy_and_carbon_consumed_handler = (
            peaktime_energy_and_carbon_consumed
        )
        self._occupancy_handler = occupancy

        for worker_node in self._worker_nodes:
            worker_node.set_datalogger_handlers(job_started, job_finished)

    def get_number_of_nodes(self):
        return len(self._worker_nodes)

    def get_number_of_cores(self):
        total = 0
        for node in self._worker_nodes:
            total += node.number_of_cores
        return total

    def submit_job(self, job):
        self._queued_jobs.append(job)
        self._job_submitted_handler(job)

    def has_queued_jobs(self):
        return len(self._queued_jobs) > 0

    def has_running_jobs(self):
        for worker_node in self._worker_nodes:
            if worker_node.busy_cores > 0:
                return True
        return False

    def clock_all_nodes(self, change, reason, steps=1):
        """Apply a frequency change (e.g. WorkerNode.clock_down) to every node and log it once."""
        unchanged = 0
        for worker_node in self._worker_nodes:
            frequency_before = worker_node.running_frequency
            for _ in range(steps):
                change(worker_node)
            unchanged += worker_node.running_frequency == frequency_before
        message = "%s: %s (%d nodes"
        args = [
            self._simulation_time.get_current_datetime(),
            reason,
            len(self._worker_nodes),
        ]
        if unchanged:
            message += ", %d of them already at that limit"
            args.append(unchanged)
        logger.log(Logging.EVENT, message + ")", *args)

    def cluster_occupancy(self):
        coresavail = 0
        coresused = 0
        for node in self._worker_nodes:
            coresavail += node.number_of_cores
            coresused += node.busy_cores
        return coresused / coresavail

    def update(self):
        # ---------------------------------
        #    Job Management Steps
        # ---------------------------------
        ### Running jobs ###

        #        if self._simulation_time.get_current_datetime().strftime('%H:%M') in ('00:00','00:01','00:02','00:03','00:04','00:05','00:06','00:07','00:08','00:09'):
        day = self._simulation_time.get_current_datetime().strftime("%d/%m/%Y")
        if day != self._last_day:
            self._days += 1
            logger.log(Logging.EVENT, "Simulation day %d: %s", self._days, day)
            self._last_day = day

        for worker_node in self._worker_nodes:
            worker_node.update()

        ### Queues ###
        # Try to start the next queued job
        next_job = self._queued_jobs.popleft() if self._queued_jobs else None
        # Try to fill nodes in order
        for worker_node in self._worker_nodes:
            while next_job is not None and worker_node.can_schedule_job(next_job):
                worker_node.start_job(next_job)
                next_job = self._queued_jobs.popleft() if self._queued_jobs else None
        # If we failed to allocate the next queued job to a node
        if next_job is not None:
            self._queued_jobs.appendleft(next_job)

        # ---------------------------------
        #    Termination Check
        # ---------------------------------
        # First end condition: When we have no jobs running and no more jobs to submit, Exit this code and don't report power metrics.
        if not self.has_running_jobs() and not self.has_queued_jobs():
            self._mission_accomplished = True
            return

        # ---------------------------------
        #    Energy Saving Try Section
        # ---------------------------------
        # Compares the simulation time wrt the time in the hh segment and moves a pointer to the correct hh segment carbon usage.
        # A timestep can span several segments, so catch up as far as needed. The start-up verification
        # guarantees a row at or after the last update, so the next segment always exists.
        while self._simulation_time.get_current_datetime() > datetime.strptime(
            self._carbondata[self._cditerant + 1][0], "%Y-%m-%dT%H:%M:%S"
        ):
            self._cditerant += 1

        # The time-of-day policies trigger on crossing a boundary since the previous update, so each
        # fires exactly once per day regardless of timestep size or start offset.
        now = self._simulation_time.get_current_datetime()
        previous_update = now - timedelta(seconds=self._simulation_time.get_timestep())

        # Code to clock down nodes between 5pm and 9pm everyday
        if "cd1721" in self._energy_saving_try:
            five_pm = now.replace(hour=17, minute=0, second=0, microsecond=0)
            nine_pm = now.replace(hour=21, minute=0, second=0, microsecond=0)
            steps = 2 if self._energy_saving_try == "cdcd1721" else 1
            if previous_update < five_pm <= now:
                self.clock_all_nodes(
                    WorkerNode.clock_down, f"5pm, clocking down {steps} step(s)", steps
                )

            if previous_update < nine_pm <= now:
                self.clock_all_nodes(
                    WorkerNode.clock_up, f"9pm, clocking up {steps} step(s)", steps
                )

        # Grid summer saving program is to clock running nodes down to their lowest values from 11:30 to 15:30
        if "middaymaxcd" in self._energy_saving_try:
            half_past_eleven = now.replace(hour=11, minute=30, second=0, microsecond=0)
            half_past_three = now.replace(hour=15, minute=30, second=0, microsecond=0)
            if previous_update < half_past_eleven <= now:
                self.clock_all_nodes(
                    WorkerNode.clock_minimum, "11:30, clocking down to the minimum"
                )

            if previous_update < half_past_three <= now:
                self.clock_all_nodes(
                    WorkerNode.clock_maximum, "15:30, clocking up to the maximum"
                )

        # Clocking down nodes when the next hh timesegment is forecast to have "high" or "very high" usage.
        # A better and more reliable way is to dampen the transition by instead using the numerical equivalent of high which is 200 (g(C02)/kWh).
        # and requiring the forecast usage to be 205 to switch into clockdown and 195 to switch out of it.
        # Even better yet, we can just a threshold that can be user generated.
        if "highforecast" in self._energy_saving_try:
            if self._anticipate_clkdown:
                self.clock_all_nodes(
                    WorkerNode.clock_down, "high forecast, clocking down 1 step"
                )
                self._anticipate_clkdown = False
                self._in_clkdown = True

            if self._anticipate_clockup:
                self.clock_all_nodes(
                    WorkerNode.clock_up, "forecast back down, clocking up 1 step"
                )
                self._anticipate_clockup = False
                self._in_clkdown = False

            if (
                self._in_clkdown == False
                and float(self._carbondata[self._cditerant + 1][1])
                > self._CIThresholdValue + 5
            ):
                logger.log(
                    Logging.EVENT,
                    "%s: forecast %s gCO2e/kWh for the next segment is above the threshold, "
                    "clocking down at the next timestep",
                    now,
                    self._carbondata[self._cditerant + 1][1],
                )
                self._anticipate_clkdown = True

            if (
                self._in_clkdown == True
                and float(self._carbondata[self._cditerant + 1][1])
                < self._CIThresholdValue - 5
            ):
                logger.log(
                    Logging.EVENT,
                    "%s: forecast %s gCO2e/kWh for the next segment is below the threshold, "
                    "clocking up at the next timestep",
                    now,
                    self._carbondata[self._cditerant + 1][1],
                )
                self._anticipate_clockup = True

        # --------------------------------------------------------
        #   Export Energy, Carbon Used and Occupancy per timestep to logger
        # --------------------------------------------------------
        for worker_node in self._worker_nodes:
            self._timestep_power_dissipated += (
                worker_node.timestep_power_dissipated()
            )  # Outputs the amount of power used by machines in a timestep in kWh.

        self._timestep_carbon_consumed = float(
            self._carbondata[self._cditerant][2]
        )  # Read in the carbon intensity of the grid at the timestep you are on.
        self._timestep_occupancy = self.cluster_occupancy()

        self._energy_and_carbon_consumed_handler(
            self._timestep_power_dissipated, self._timestep_carbon_consumed
        )  # Passing energy consumed and the carbon intensity per timestep
        self._occupancy_handler(
            self._timestep_occupancy
        )  # Passing occupancy per timestep

        if "middaymaxcd" in self._energy_saving_try:
            if (
                datetime.strptime("11:30:00", "%H:%M:%S").time()
                < self._simulation_time.get_current_datetime().time()
                < datetime.strptime("15:30:00", "%H:%M:%S").time()
            ):
                self._peaktime_energy_and_carbon_consumed_handler(
                    self._timestep_power_dissipated, self._timestep_carbon_consumed
                )

        elif (
            datetime.strptime("17:00:00", "%H:%M:%S").time()
            < self._simulation_time.get_current_datetime().time()
            < datetime.strptime("21:00:00", "%H:%M:%S").time()
        ):
            self._peaktime_energy_and_carbon_consumed_handler(
                self._timestep_power_dissipated, self._timestep_carbon_consumed
            )

        # print(self._timestep_power_dissipated) #For debugging
        self._timestep_power_dissipated = 0  # Reset the accumulator every time-step

    @property
    def energy_saving_try(self):
        return self._energy_saving_try
