# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY 
#                     and the University of Glasgow
# Authors: Dwayne Spiteri and Gordon Stewart.
# For more information about rights and fair use please refer to src/Main.py.
# For full detailed and legal infomration please read the LICENSE and NOTICE
#    files in the main directory 
# ===========================================================================

from util import Logging
import json
import os

logger = Logging.get_logger()


class DataLogger():

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

        # verbosity
        self._verbosity = config["output"]["verbosity"]
        self._run_dir = config["output"].get("run_dir", "logs")
        self._simulation_parameters = {}


    def set_simulation_parameters(self, simulation_parameters):
        self._simulation_parameters = simulation_parameters


    def job_submit(self, job):
        pass


    def job_start(self, job, worker_node):
        if self._verbosity in ["high"]:
            logger.info(f'Starting job {job} on node {worker_node.hostname} at {job.start_time}')
        self._jobs_started += 1
        self._jobs_total_cores_used += job.cores_req


    def job_finish(self, job, worker_node):
        if self._verbosity in ["high"]:
            logger.info(f'Job {job} finished on node {worker_node.hostname} at {job.end_time}')
        self._jobs_finished += 1
        self._cumulative_wallclock_time += job.duration
        # Yes, Sam, I know... ;-)
        self._cumulative_cpu_time += job.duration * job.cores_req

    def energy_and_carbon_consumed(self, timestep_energy_consumed, timestep_carbon_consumed_per_unit_energy):
        '''
        This should pass power dissipated in per timestep (kWh) such that the total consumption is in kiloWatt-hours
        This should pass carbon consumed in per timestep (g/kWh) such that the total consumption is in grams/kiloWatt-hours
        '''
        #logger.info(f'Cluster {cluster} consumed {cluster.instantaneous_power_consumed} W')
        self._total_energy_consumed += timestep_energy_consumed # kWh
        self._total_carbon_consumed += timestep_energy_consumed * timestep_carbon_consumed_per_unit_energy #g/kWh

    def peaktime_energy_and_carbon_consumed(self, timestep_energy_consumed, timestep_carbon_consumed_per_unit_energy):
        '''
        This should pass power dissipated in per timestep (kWh) such that the total consumption is in kiloWatt-hours
        This should pass carbon consumed in per timestep (g/kWh) such that the total consumption is in grams/kiloWatt-hours
        '''
        self._peaktime_energy_consumed += timestep_energy_consumed # kWh
        self._peaktime_carbon_consumed += timestep_energy_consumed * timestep_carbon_consumed_per_unit_energy #g/kWh  
    
    def sum_occupancy(self, timestep_occupancy):
        '''
        This should store the sum of the occupancy every timestep (to be divided by the number of timesteps when the simulation ends)
        '''
        self._sum_occupancy += timestep_occupancy # kWh

    def _average_core_hours(self):
        if self._jobs_total_cores_used == 0:
            return 0
        return (self._cumulative_cpu_time/3600) / self._jobs_total_cores_used

    def _peaktime_carbon_percent(self):
        if self._total_carbon_consumed == 0:
            return 0
        return self._peaktime_carbon_consumed/self._total_carbon_consumed*100

    def print_summary(self, summary_file, additional_description, total_simulated_time, timestepinsec, total_real_time ):
        # A run can end with no jobs started (or at t=0), so guard every per-job average.
        self._avg_jobs_completed = self._jobs_finished + (self._jobs_started - self._jobs_finished)/2
        self._avg_energy_per_job = self._total_energy_consumed/self._avg_jobs_completed if self._avg_jobs_completed else 0
        self._avg_carbon_per_job = self._total_carbon_consumed/self._avg_jobs_completed if self._avg_jobs_completed else 0
        timesteps_elapsed        = total_simulated_time/timestepinsec
        self._avg_occupancy      = self._sum_occupancy/timesteps_elapsed if timesteps_elapsed else 0
        summary = self._create_summary(total_simulated_time, total_real_time)

        print(f'========')
        print(f'Summary')
        print(f'========')
        print(f'')   
        print(f'Total Simulated-time Duration      : {total_simulated_time/3600:4.1f} hours')
        print(f'Total Real-time Duration           : {total_real_time/60:4.1f} minutes')
        print(f'')
        #print(f'')
        #print(f'Submitted: {self._jobs_submitted}')
        print(f'Jobs Started                       : {self._jobs_started}')
        print(f'Jobs Finished                      : {self._jobs_finished}')
        #print(f'Failed:    {self._jobs_failed}')
        #print(f'Aborted:   {self._jobs_aborted}')
        print(f'')
        print(f'Total CPU duration                 : {self._cumulative_cpu_time/3600:6.1f} hours')
        print(f'Average CPU duration               : {self._average_core_hours():4.2f} hours')
        print(f'Average Occupancy of all clusters  : {(self._avg_occupancy*100):3.1f} %')
        print(f'')        
        print(f'Total energy consumed by compute   : {self._total_energy_consumed:3.2f} kWh')
        print(f'Peaktime (5-9pm) energy consumption: {self._peaktime_energy_consumed:3.2f} kWh')
        print(f'Average energy consumption per job : {self._avg_energy_per_job*1e3:3.2f} Wh')
        print(f'')
        print(f'Estimated CO2e emissions           : {self._total_carbon_consumed/1e3:.3f} kg')
        print(f'Estimated Peaktime CO2e emissions  : {self._peaktime_carbon_consumed/1e3:.3f} kg')
        print(f'Average CO2e emissions per job     : {self._avg_carbon_per_job:.3f} g')
        print(f'Peaktime CO2e emissions percentage : {self._peaktime_carbon_percent():.3f} %')
        print(f'')
        
        if summary_file == True:
            summary_path = os.path.join(self._run_dir, 'summary.txt')
            with open(summary_path, 'a') as outfile:
                outfile.write(f'========\n')
                outfile.write(f'Summary\n')
                outfile.write(f'========\n')
                outfile.write(f'\n')
                outfile.write(f'Total Simulated-time Duration      : {total_simulated_time/3600:4.1f} hours\n')
                outfile.write(f'Total Real-time Duration           : {total_real_time/60:4.1f} minutes\n')
                outfile.write(f'\n')                
                #outfile.write(f'Submitted: {self._jobs_submitted}\n')
                outfile.write(f'Jobs Started                       : {self._jobs_started}\n')
                outfile.write(f'Jobs Finished                      : {self._jobs_finished}\n')
                #outfile.write(f'Failed:    {self._jobs_failed}\n')
                #outfile.write(f'Aborted:   {self._jobs_aborted}\n')
                outfile.write(f'\n')
                outfile.write(f'Total CPU duration                 : {self._cumulative_cpu_time/3600:6.1f} hours\n')
                outfile.write(f'Average CPU duration               : {self._average_core_hours():4.2f} hours\n')
                outfile.write(f'Average Occupancy of all clusters  : {(self._avg_occupancy*100):3.1f} %\n')
                outfile.write(f'\n')
                outfile.write(f'Total energy consumed by compute   : {self._total_energy_consumed:3.2f} kWh\n')
                outfile.write(f'Peaktime (5-9pm) energy consumption: {self._peaktime_energy_consumed:3.2f} kWh\n')
                outfile.write(f'Average energy consumption per job : {self._avg_energy_per_job*1e3:3.2f} Wh\n')              
                outfile.write(f'\n')
                outfile.write(f'Estimated CO2e emissions           : {self._total_carbon_consumed/1e3:.3f} kg\n')
                outfile.write(f'Estimated Peaktime CO2e emissions  : {self._peaktime_carbon_consumed/1e3:.3f} kg\n')
                outfile.write(f'Average CO2e emissions per job     : {self._avg_carbon_per_job:.3f} g\n')
                outfile.write(f'Peaktime CO2e emissions percentage : {self._peaktime_carbon_percent():.3f} %\n')
                outfile.write(f'\n')

            summary_json_path = os.path.join(self._run_dir, 'summary.json')
            with open(summary_json_path, 'w') as outfile:
                json.dump(summary, outfile, indent=4)
                outfile.write('\n')


    def _create_summary(self, total_simulated_time, total_real_time):
        return {
            "simulation_parameters": self._simulation_parameters,
            "duration": {
                "simulated_seconds": total_simulated_time,
                "simulated_hours": total_simulated_time/3600,
                "real_seconds": total_real_time,
                "real_minutes": total_real_time/60,
            },
            "jobs": {
                "started": self._jobs_started,
                "finished": self._jobs_finished,
                "average_completed": self._avg_jobs_completed,
                "total_cores_used": self._jobs_total_cores_used,
            },
            "cpu": {
                "total_core_seconds": self._cumulative_cpu_time,
                "total_core_hours": self._cumulative_cpu_time/3600,
                "average_core_hours": self._average_core_hours(),
            },
            "occupancy": {
                "average_fraction": self._avg_occupancy,
                "average_percent": self._avg_occupancy*100,
            },
            "energy": {
                "total_kwh": self._total_energy_consumed,
                "peaktime_kwh": self._peaktime_energy_consumed,
                "average_per_job_wh": self._avg_energy_per_job*1e3,
            },
            "carbon": {
                "total_g": self._total_carbon_consumed,
                "total_kg": self._total_carbon_consumed/1e3,
                "peaktime_g": self._peaktime_carbon_consumed,
                "peaktime_kg": self._peaktime_carbon_consumed/1e3,
                "average_per_job_g": self._avg_carbon_per_job,
                "peaktime_percent": self._peaktime_carbon_percent(),
            },
        }
