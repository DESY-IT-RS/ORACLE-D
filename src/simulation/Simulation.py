# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY
#                     and the University of Glasgow
# For more information about rights and fair use please refer to src/Main.py.
# For full detailed and legal information please read the LICENSE and NOTICE
#    files in the main directory
# ===========================================================================


import os
import sys
from datetime import datetime, timedelta

from cluster.Cluster import Cluster
from cluster.WorkerNode import WorkerNode
from datalogger.DataLogger import DataLogger
from jobs.JobScheduler import JobScheduler
from simulation.Time import SimulationTime
from util import Logging

logger = Logging.get_logger()


class Simulation:
    def __init__(self, config, inventory, worker_nodes, carbon_intensity_data):

        self.desiredStartTime = config[
            "Simulation"
        ][
            "desired_starttime"
        ]  # STEVE '2018-01-01 00:30' : Starts at the simulation at a set time can be set to any time you wish in the format '2024-01-12 15:00'
        self._simulation_time = SimulationTime(
            config, self.desiredStartTime
        )  # If you want this to be set to the current time, set desiredStartTime to None
        self._simulation_length = config[
            "Simulation"
        ][
            "simulation_length"
        ]  # Desired maximum length of the simulation in seconds. (For one year 365*24*3600)
        self._simulation_time._timestep_seconds = config["Simulation"][
            "timestep"
        ]  # Simulation time step in seconds. #Steve was using 200
        # Finds the half-hour time segment to which the start of the simulation belongs and the one after the end time.
        self._simulation_starting_segment = self._simulation_time.find_hh_segment(
            self._simulation_time._time
        )
        self._simulation_maxfinal_segment = self._simulation_time.find_hh_segment(
            self._simulation_time._time + timedelta(seconds=self._simulation_length),
            "next",
        )

        self._run_dir = config["output"].get("run_dir")

        # Carbon Intensity data (gCO2/kWh), checked and loaded by util.Verification: one row per segment
        # from the start segment up to the first row at or after the last update of the simulation.
        datapath = config["carbon_intensity"]["folder"]
        datafile = config["carbon_intensity"]["filename"]
        # Convert start and end segment datetimes to format found in datafile.
        self.datastart_str = datetime.strftime(
            self._simulation_starting_segment, "%Y-%m-%dT%H:%M:%S"
        )
        self.datafinal_str = datetime.strftime(
            self._simulation_maxfinal_segment, "%Y-%m-%dT%H:%M:%S"
        )
        self._CIntendata = carbon_intensity_data

        self.CIThresholdValue = config[
            "carbon_intensity"
        ][
            "high_CI_threshold"
        ]  #  200gCO2e/kWh - This roughly corresponds to what is labeled 'high' in the UK. For Germany, I'll put this at 400

        # Create the cluster {WorkerNode[instantiated WN of type WorkerNode]:amount[integer]}
        # Types of nodes you can currently use are {WorkerNode_h16, WorkerNode_h17, WorkerNode_d20, WorkerNode_d21, WorkerNode_d22, WorkerNode_a23},
        # the details of which can be accessed in node().system, node().cpu, and node().year.
        # You now pass the carbon data you need to estimate the amount of carbon used (manditory)
        # and a flag to set the option of how you will change the operation of the servers during runtime (none, cd1721, cdcd1721 and highforecast) (optional)

        # EXAMPLES
        # Glasgow Uni
        # self._cluster = Cluster(self._simulation_time, {WorkerNode_h16:13,WorkerNode_h17:43, WorkerNode_d20:40, WorkerNode_d21:32, WorkerNode_d22:36}, self._CIntendata, 'none')
        # self._cluster = Cluster(self._simulation_time, {WorkerNode_d20:40, WorkerNode_d21:32, WorkerNode_d22:36, WorkerNode_d24:17}, self._CIntendata, 'none') # Future 1
        # self._cluster = Cluster(self._simulation_time, {WorkerNode_d20:40, WorkerNode_d21:32, WorkerNode_d22:36, WorkerNode_a24:17}, self._CIntendata, 'none') # Future 2
        # DESY
        self._cluster = Cluster(
            config,
            self._simulation_time,
            inventory,
            worker_nodes,
            self._CIntendata,
            config["Simulation"]["savings_policy"],
            self.CIThresholdValue,
        )  # Starting DESY

        self._peaktime_str = None
        if "middaymaxcd" in config["Simulation"]["savings_policy"]:
            self._peaktime_str = "11:30-15:30"
        else:
            self._peaktime_str = "17:00-21:00"

        # Class to record statistics
        self._datalogger = DataLogger(config)
        self._cluster.set_datalogger_handlers(
            self._datalogger.job_submit,
            self._datalogger.job_start,
            self._datalogger.job_finish,
            self._datalogger.energy_and_carbon_consumed,
            self._datalogger.peaktime_energy_and_carbon_consumed,
            self._datalogger.sum_occupancy,
        )

        # Create a job scheduler to initally seed the cluster with jobs and provide jobs on a regular notice. Needs to know about this cluster
        # Format for initial jobs is a dictionary of {'VO1':jobs, 'VO2':jobs, [...]}
        # Format for regular jobs is a list  of lists of a dictionary of [[{'VO1':jobs per X seconds, 'VO2':jobs per X seconds, [...]}, X], [....] ]
        # self._jobScheduler = JobScheduler(self._simulation_time, self._cluster, {'GridPP':10} , None)
        if config["jobs"]["regular_incoming_mix"] == {}:
            jobs_refill = None
        else:
            jobs_refill = [
                [
                    config["jobs"]["regular_incoming_mix"],
                    config["jobs"]["incoming_timestep"],
                ]
            ]

        self._jobScheduler = JobScheduler(
            self._simulation_time,
            self._cluster,
            config["jobs"]["initial_mix"],
            jobs_refill,
        )
        # self._jobScheduler = JobScheduler(self._simulation_time, self._cluster, {'GridPP':100000}, [[{'GridPP':250}, 3600*10]])
        self._rundescript = config[
            "output"
        ][
            "run_label"
        ]  # Add here a description of what kind of jobs you are running. "RF20PMTest-50000LHCJobs-Base" for example

        # The parameters are part of the run output, whatever the log verbosity.
        simulation_parameters = self._get_simulation_parameters(datapath, datafile)
        self._datalogger.set_simulation_parameters(simulation_parameters)
        simulation_parameters_text = self._format_simulation_parameters(
            simulation_parameters
        )
        logger.info(
            "Created simulation with parameters:\n%s", simulation_parameters_text
        )
        self._write_simulation_parameters(simulation_parameters_text)

    def _log_finished(self):
        logger.info("Simulation finished. Output written to %s", self._run_dir)

    def _write_simulation_parameters(self, simulation_parameters):
        run_dir = self._datalogger._run_dir
        if run_dir:
            with open(os.path.join(run_dir, "parameters.txt"), "w") as outfile:
                outfile.write(simulation_parameters)
                outfile.write("\n")

    def _get_simulation_parameters(self, carbon_data_path, carbon_data_file):
        regular_jobs = []
        if self._jobScheduler._regular_incoming_jobs:
            regular_jobs = [
                {
                    "job_mix": job_mix,
                    "incoming_timestep_seconds": secs,
                }
                for job_mix, secs in self._jobScheduler._regular_incoming_jobs
            ]

        return {
            "start_time": str(self._simulation_time.get_start_datetime()),
            "max_end_time": str(
                self._simulation_time.get_start_datetime()
                + timedelta(seconds=self._simulation_length)
            ),
            "simulation_length_seconds": self._simulation_length,
            "timestep_seconds": self._simulation_time.get_timestep(),
            "savings_policy": self._cluster._energy_saving_try,
            "carbon_intensity": {
                "file": f"{carbon_data_path}{carbon_data_file}",
                "segments": {
                    "start": self.datastart_str,
                    "end": self.datafinal_str,
                },
                "high_CI_threshold": self.CIThresholdValue,
            },
            "cluster": {
                "worker_nodes": self._cluster.get_number_of_nodes(),
                "worker_cores": self._cluster.get_number_of_cores(),
                "worker_node_inventory": self._cluster._worker_node_inventory,
            },
            "jobs": {
                "initial": self._jobScheduler._inital_job_mix,
                "regular_incoming": regular_jobs,
            },
        }

    def _format_simulation_parameters(self, simulation_parameters):
        carbon_intensity = simulation_parameters["carbon_intensity"]
        cluster = simulation_parameters["cluster"]
        jobs = simulation_parameters["jobs"]
        regular_jobs = "none"
        if jobs["regular_incoming"]:
            regular_jobs = ", ".join(
                f"{vo}: {count} per {regular_job['incoming_timestep_seconds']} seconds"
                for regular_job in jobs["regular_incoming"]
                for vo, count in regular_job["job_mix"].items()
            )

        return "\n".join(
            [
                f"  start_time: {simulation_parameters['start_time']}",
                f"  max_end_time: {simulation_parameters['max_end_time']}",
                f"  simulation_length_seconds: {simulation_parameters['simulation_length_seconds']}",
                f"  timestep_seconds: {simulation_parameters['timestep_seconds']}",
                f"  savings_policy: {simulation_parameters['savings_policy']}",
                f"  carbon_intensity_file: {carbon_intensity['file']}",
                f"  carbon_intensity_segments: {carbon_intensity['segments']['start']} to {carbon_intensity['segments']['end']}",
                f"  high_CI_threshold: {carbon_intensity['high_CI_threshold']}",
                f"  worker_nodes: {cluster['worker_nodes']}",
                f"  worker_cores: {cluster['worker_cores']}",
                f"  worker_node_inventory: {self._format_job_mix(cluster['worker_node_inventory'])}",
                f"  initial_jobs: {self._format_job_mix(jobs['initial'])}",
                f"  regular_incoming_jobs: {regular_jobs}",
            ]
        )

    def _format_job_mix(self, job_mix):
        if not job_mix:
            return "none"
        return ", ".join(f"{vo}: {jobs}" for vo, jobs in job_mix.items())

    def start(self):
        # Permanently run nodes clocked down.
        if self._cluster._energy_saving_try in ("cd", "cdcd"):
            steps = len(self._cluster._energy_saving_try) // 2
            self._cluster.clock_all_nodes(
                WorkerNode.clock_down,
                f"clocking down {steps} step(s) for the whole run",
                steps,
            )
        logger.info("Simulation started.")

        while True:
            simtottime = (
                self._simulation_time.get_current_datetime()
                - self._simulation_time.get_start_datetime()
            )  # Simulated Time

            # Update the state of the scheduler
            self._jobScheduler.update()

            # Update the state of the cluster
            self._cluster.update()

            # First end condition: When we have no jobs running and no more jobs to submit. Flag will be activate in the cluster update.
            if self._cluster._mission_accomplished == True:
                realtottime = (
                    datetime.now() - self._simulation_time.get_origin_datetime()
                )  # Real Time
                logger.info(
                    "No jobs left to run or queue; ending the simulation at %s.",
                    self._simulation_time.get_current_datetime(),
                )
                self._datalogger.print_summary(
                    True,
                    self._rundescript,
                    self._peaktime_str,
                    simtottime.total_seconds(),
                    self._simulation_time.get_timestep(),
                    realtottime.total_seconds(),
                )
                self._log_finished()
                sys.exit()

            # Second end condition: simulation_length seconds of simulation time have passed.
            if simtottime.total_seconds() >= self._simulation_length:
                realtottime = (
                    datetime.now() - self._simulation_time.get_origin_datetime()
                )  # Real Time
                logger.info(
                    "Reached the simulation length of %s s; ending the simulation at %s.",
                    self._simulation_length,
                    self._simulation_time.get_current_datetime(),
                )
                self._datalogger.print_summary(
                    True,
                    self._rundescript,
                    self._peaktime_str,
                    simtottime.total_seconds(),
                    self._simulation_time.get_timestep(),
                    realtottime.total_seconds(),
                )
                self._log_finished()
                sys.exit()

            # Move forward in time
            self._simulation_time.advance()
