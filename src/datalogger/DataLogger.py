# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY
#                     and the University of Glasgow
# Authors: Dwayne Spiteri and Gordon Stewart.
# For more information about rights and fair use please refer to src/Main.py.
# For full detailed and legal infomration please read the LICENSE and NOTICE
#    files in the main directory
# ===========================================================================

import json
import os

from util import Logging

logger = Logging.get_logger()


class DataLogger:
    # This should also write to disk...
    def __init__(self, config):
        self._jobs_submitted = 0
        self._jobs_started = 0
        self._jobs_finished = 0
        self._jobs_failed = 0
        self._jobs_aborted = 0
        self._jobs_total_cores_used = 0

        # Could store these by job type...
        self._cumulative_cpu_time = 0
        self._cumulative_wallclock_time = 0
        self._total_energy_consumed = 0
        self._peaktime_energy_consumed = 0
        self._total_carbon_consumed = 0
        self._peaktime_carbon_consumed = 0
        self._sum_occupancy = 0

        # Averages
        self._avg_jobs_completed = 0
        self._avg_energy_per_job = 0
        self._avg_carbon_per_job = 0
        self._avg_occupancy = 0

        self._run_dir = config["output"].get("run_dir", "logs")
        self._simulation_parameters = {}

    def set_simulation_parameters(self, simulation_parameters):
        self._simulation_parameters = simulation_parameters

    def job_submit(self, job):
        pass

    def job_start(self, job, worker_node):
        logger.log(
            Logging.DETAIL,
            "Starting job %s on node %s at %s",
            job,
            worker_node.hostname,
            job.start_time,
        )
        self._jobs_started += 1
        self._jobs_total_cores_used += job.cores_req

    def job_finish(self, job, worker_node):
        logger.log(
            Logging.DETAIL,
            "Job %s finished on node %s at %s",
            job,
            worker_node.hostname,
            job.end_time,
        )
        self._jobs_finished += 1
        self._cumulative_wallclock_time += job.duration
        # Yes, Sam, I know... ;-)
        self._cumulative_cpu_time += job.duration * job.cores_req

    def energy_and_carbon_consumed(
        self, timestep_energy_consumed, timestep_carbon_consumed_per_unit_energy
    ):
        """
        This should pass power dissipated in per timestep (kWh) such that the total consumption is in kiloWatt-hours
        This should pass carbon consumed in per timestep (g/kWh) such that the total consumption is in grams/kiloWatt-hours
        """
        # logger.info(f'Cluster {cluster} consumed {cluster.instantaneous_power_consumed} W')
        self._total_energy_consumed += timestep_energy_consumed  # kWh
        self._total_carbon_consumed += (
            timestep_energy_consumed * timestep_carbon_consumed_per_unit_energy
        )  # g/kWh

    def peaktime_energy_and_carbon_consumed(
        self, timestep_energy_consumed, timestep_carbon_consumed_per_unit_energy
    ):
        """
        This should pass power dissipated in per timestep (kWh) such that the total consumption is in kiloWatt-hours
        This should pass carbon consumed in per timestep (g/kWh) such that the total consumption is in grams/kiloWatt-hours
        """
        self._peaktime_energy_consumed += timestep_energy_consumed  # kWh
        self._peaktime_carbon_consumed += (
            timestep_energy_consumed * timestep_carbon_consumed_per_unit_energy
        )  # g/kWh

    def sum_occupancy(self, timestep_occupancy):
        """
        This should store the sum of the occupancy every timestep (to be divided by the number of timesteps when the simulation ends)
        """
        self._sum_occupancy += timestep_occupancy  # kWh

    def print_summary(
        self,
        summary_file,
        additional_description,
        peaktime_str,
        total_simulated_time,
        timestepinsec,
        total_real_time,
    ):
        self._avg_jobs_completed = (
            self._jobs_finished + (self._jobs_started - self._jobs_finished) / 2
        )
        self._avg_energy_per_job = (
            self._total_energy_consumed / self._avg_jobs_completed
        )
        self._avg_carbon_per_job = (
            self._total_carbon_consumed / self._avg_jobs_completed
        )
        self._avg_occupancy = self._sum_occupancy / (
            total_simulated_time / timestepinsec
        )
        summary = self._create_summary(total_simulated_time, total_real_time)

        summary_text = self._format_summary(summary, peaktime_str)
        logger.info("\n%s", summary_text)

        if summary_file:
            summary_path = os.path.join(self._run_dir, "summary.txt")
            with open(summary_path, "a") as outfile:
                outfile.write(summary_text)
                outfile.write("\n")

            summary_json_path = os.path.join(self._run_dir, "summary.json")
            with open(summary_json_path, "w") as outfile:
                json.dump(summary, outfile, indent=4)
                outfile.write("\n")

    def _format_summary(self, summary, peaktime_str):
        """The human-readable summary, as written to summary.txt and logged."""
        duration, jobs, cpu = summary["duration"], summary["jobs"], summary["cpu"]
        occupancy, energy, carbon = (
            summary["occupancy"],
            summary["energy"],
            summary["carbon"],
        )
        return "\n".join(
            [
                "========",
                "Summary",
                "========",
                "",
                f"Total Simulated-time Duration              : {duration['simulated_hours']:4.1f} hours",
                f"Total Real-time Duration                   : {duration['real_minutes']:4.1f} minutes",
                "",
                f"Jobs Started                               : {jobs['started']}",
                f"Jobs Finished                              : {jobs['finished']}",
                "",
                f"Total CPU duration                         : {cpu['total_core_hours']:6.1f} hours",
                f"Average CPU duration                       : {cpu['average_core_hours']:4.2f} hours",
                f"Average Occupancy of all clusters          : {occupancy['average_percent']:3.1f} %",
                "",
                f"Total energy consumed by compute           : {energy['total_kwh']:3.2f} kWh",
                f"Peaktime ({peaktime_str}) energy consumption  : {energy['peaktime_kwh']:3.2f} kWh",
                f"Average energy consumption per job         : {energy['average_per_job_wh']:3.2f} Wh",
                "",
                f"Estimated CO2e emissions                   : {carbon['total_kg']:.3f} kg",
                f"Estimated Peaktime CO2e emissions          : {carbon['peaktime_kg']:.3f} kg",
                f"Average CO2e emissions per job             : {carbon['average_per_job_g']:.3f} g",
                f"Peaktime CO2e emissions percentage         : {carbon['peaktime_percent']:.3f} %",
                "",
            ]
        )

    def _create_summary(self, total_simulated_time, total_real_time):
        return {
            "simulation_parameters": self._simulation_parameters,
            "duration": {
                "simulated_seconds": total_simulated_time,
                "simulated_hours": total_simulated_time / 3600,
                "real_seconds": total_real_time,
                "real_minutes": total_real_time / 60,
            },
            "jobs": {
                "started": self._jobs_started,
                "finished": self._jobs_finished,
                "average_completed": self._avg_jobs_completed,
                "total_cores_used": self._jobs_total_cores_used,
            },
            "cpu": {
                "total_core_seconds": self._cumulative_cpu_time,
                "total_core_hours": self._cumulative_cpu_time / 3600,
                "average_core_hours": (self._cumulative_cpu_time / 3600)
                / self._jobs_total_cores_used,
            },
            "occupancy": {
                "average_fraction": self._avg_occupancy,
                "average_percent": self._avg_occupancy * 100,
            },
            "energy": {
                "total_kwh": self._total_energy_consumed,
                "peaktime_kwh": self._peaktime_energy_consumed,
                "average_per_job_wh": self._avg_energy_per_job * 1e3,
            },
            "carbon": {
                "total_g": self._total_carbon_consumed,
                "total_kg": self._total_carbon_consumed / 1e3,
                "peaktime_g": self._peaktime_carbon_consumed,
                "peaktime_kg": self._peaktime_carbon_consumed / 1e3,
                "average_per_job_g": self._avg_carbon_per_job,
                "peaktime_percent": self._peaktime_carbon_consumed
                / self._total_carbon_consumed
                * 100,
            },
        }
