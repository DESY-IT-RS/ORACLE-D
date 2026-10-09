# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY 
#                     and the University of Glasgow
# Authors: Dwayne Spiteri and Gordon Stewart.
# For more information about rights and fair use please refer to src/Main.py.
# For full detailed and legal infomration please read the LICENSE and NOTICE
#    files in the main directory 
# ===========================================================================

from collections import deque
import sys

from cluster.WorkerNode import *
from util import Logging
from datalogger.DataLogger import DataLogger
from datetime import datetime


logger = Logging.get_logger()


class Cluster():

    def __init__(self, config, simulation_time, worker_node_inventory, C_Intensity_data, esgimmick, C_Intensity_Threshold_Value = 200):
        ''' Creates the cluster to be simulated. 
        The first argument (simulation_time) is the common simulation time.  
        The second argument (worker_node_inventory) a dictionary of {WorkerNode:int, ...} where user specifies node type that will become the class Workernode() and the number of those nodes.
            I.e specs = {WorkerNode_d20:40, WorkerNode_d21:32, WorkerNode_d22:36}
        The third argument (C_Intensity_data) is the list that contains the carbon intensity data.   
        The fourth argument (esgimmick) is a string that represents the experiment you want to run with the cluster.
        The fifth argument (C_Intensity_Threshold_Value) is the value of the carbon intensity you want the energy saving attempt to kick in   
        '''
        
        self._simulation_time = simulation_time
        self._worker_nodes = []
        self._queued_jobs = deque()
        self._timestep_power_dissipated = 0
        self._timestep_carbon_consumed = 0 
        self._timestep_occupancy = 0
        self._days = 0
        self._last_day = ''

        self._job_submitted_handler = None
        self._energy_and_carbon_consumed_handler = None
        self._peaktime_energy_and_carbon_consumed_handler = None
        self._occupancy_handler = None
        
        self._carbondata = C_Intensity_data
        self._energy_saving_try = esgimmick
        self._cditerant = 0  # Create a iterant that marks place in the carbon data list w.r.t simulation time to be incrimented w.r.t the timestep of the simulation.
        self._CIThresholdValue = C_Intensity_Threshold_Value
        self._in_clkdown = False # Flags to make decisions based on the status of the cluster.
        self._anticipate_clkdown = False
        self._anticipate_clockup = False
  
        self._mission_accomplished = False # State of completion for the simulation. 
        self._worker_node_inventory = worker_node_inventory

        self._verbosity = config["output"]["verbosity"]
		
        # Create worker nodes from specifications. 
        for node, quantity in worker_node_inventory.items():
            for node_number in range(quantity):
                # Adds quantity number of nodes you have specified in the Simulation.
                self._worker_nodes.append(node(self._simulation_time, f'-{node_number+1:03}'))

        if self._verbosity in ["high", "medium"]:
            logger.info(f'Created cluster with {self.get_number_of_nodes()} worker nodes and {self.get_number_of_cores()} cores')


    def set_datalogger_handlers(self, job_submitted, job_started, job_finished, energy_and_carbon_consumed, peaktime_energy_and_carbon_consumed, occupancy):
        self._job_submitted_handler = job_submitted
        self._energy_and_carbon_consumed_handler = energy_and_carbon_consumed
        self._peaktime_energy_and_carbon_consumed_handler = peaktime_energy_and_carbon_consumed
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
    

    def cluster_occupancy(self):
        occ = 0
        coresavail = 0
        coresused = 0
        for node in self._worker_nodes:
            coresavail += node.number_of_cores
            coresused += node.busy_cores
        occ = coresused/coresavail
        return occ

    def update(self):
        # ---------------------------------
        #    Job Management Steps 
        # ---------------------------------        
        ### Running jobs ###
        
#        if self._simulation_time.get_current_datetime().strftime('%H:%M') in ('00:00','00:01','00:02','00:03','00:04','00:05','00:06','00:07','00:08','00:09'):
        day = self._simulation_time.get_current_datetime().strftime('%d/%m/%Y')
        if day != self._last_day:
            self._days += 1
            print(day + ': Simulation Day ' + str(self._days) )
            self._last_day = day

        for worker_node in self._worker_nodes:
            worker_node.update()
            
        ### Queues ###
        # Try to start the next queued job
        next_job = self._queued_jobs.popleft()
        # Try to fill nodes in order
        for worker_node in self._worker_nodes:
            if next_job is not None and worker_node.can_schedule_job(next_job):
                worker_node.start_job(next_job)
                next_job = self._queued_jobs.popleft()
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
        if self._simulation_time.get_current_datetime() > datetime.strptime(self._carbondata[self._cditerant+1][0], '%Y-%m-%dT%H:%M:%S'):
            self._cditerant += 1
        # Code to clock down nodes between 5pm and 9pm everyday  
        if 'cd1721' in self._energy_saving_try:             
            if self._simulation_time.get_current_datetime().strftime('%H:%M') in ('17:00','17:01','17:02','17:03','17:04','17:05','17:06','17:07','17:08', '17:09'):
                print("It's 5pm time to clock down the nodes!")
                for worker_node in self._worker_nodes:
                    worker_node.clock_down()
                    if self._energy_saving_try == 'cdcd1721': worker_node.clock_down()

            if self._simulation_time.get_current_datetime().strftime('%H:%M') in ('21:00','21:01','21:02','21:03','21:04','21:05','21:06','21:07','21:08','21:09'):
                print("It's 9pm time to clock up the nodes!")
                for worker_node in self._worker_nodes:
                    worker_node.clock_up()
                    if self._energy_saving_try == 'cdcd1721': worker_node.clock_up() 
        
        # Clocking down nodes when the next hh timesegment is forecast to have "high" or "very high" usage.
        # A better and more reliable way is to dampen the transition by instead using the numerical equivalent of high which is 200 (g(C02)/kWh).
        # and requiring the forecast usage to be 205 to switch into clockdown and 195 to switch out of it.
        # Even better yet, we can just a threshold that can be user generated.  
        if 'highforecast' in self._energy_saving_try:                 
            if self._anticipate_clkdown == True:
                for worker_node in self._worker_nodes: worker_node.clock_down()
                self._anticipate_clkdown = False
                self._in_clkdown = True

            if self._anticipate_clockup == True: 
                for worker_node in self._worker_nodes: worker_node.clock_up()
                self._anticipate_clockup = False
                self._in_clkdown = False

            if self._in_clkdown == False and float(self._carbondata[self._cditerant+1][1]) > self._CIThresholdValue+5:
                print("Usage is expected to be high, next timestep we'll clock down the nodes.")
                self._anticipate_clkdown = True

            if self._in_clkdown == True and float(self._carbondata[self._cditerant+1][1]) < self._CIThresholdValue-5:
                print("Usage is going down, next timestep we'll clock up the nodes.")
                self._anticipate_clockup = True                

        # --------------------------------------------------------
        #   Export Energy, Carbon Used and Occupancy per timestep to logger
        # --------------------------------------------------------
        for worker_node in self._worker_nodes:        
            self._timestep_power_dissipated += worker_node.timestep_power_dissipated() # Outputs the amount of power used by machines in a timestep in kWh. 

        self._timestep_carbon_consumed = float(self._carbondata[self._cditerant][2]) # Read in the carbon intensity of the grid at the timestep you are on.
        self._timestep_occupancy = self.cluster_occupancy()

        self._energy_and_carbon_consumed_handler(self._timestep_power_dissipated, self._timestep_carbon_consumed) # Passing energy consumed and the carbon intensity per timestep
        self._occupancy_handler(self._timestep_occupancy)  # Passing occupancy per timestep

        if datetime.strptime('17:00:00', '%H:%M:%S').time() < self._simulation_time.get_current_datetime().time() < datetime.strptime('21:00:00', '%H:%M:%S').time():
            self._peaktime_energy_and_carbon_consumed_handler(self._timestep_power_dissipated, self._timestep_carbon_consumed) 
        
        #print(self._timestep_power_dissipated) #For debugging
        self._timestep_power_dissipated = 0 # Reset the accumulator every time-step
      
    

