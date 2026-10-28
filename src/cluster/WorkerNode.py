# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Dwayne Spiteri and Gordon Stewart.
# For more information about rights and fair use please refer to src/Main.py.
# For full detailed and legal infomration please read the LICENCE and NOTICE
#    files in the main directory 
# ===========================================================================

from util import Logging
logger = Logging.get_logger()


class WorkerNode():

    def __init__(self, simulation_time, hostname='', threads=0, memory=0, idlepower=0, freq_dep_specs={3.0:(300,3000), 2.0:(200,2000), 1.0:(100,1000)}):
        '''Creates a worker node to be simulated.
        The first argument (simulation_time) is the common simulation time.
        The second argument (hostname)       is the name of the worker node.
        The third argument (threads)         is the number of threads the machine has - usually this is equal to or double the number of cores (default is double)
        The fourth argument (memory)         is the about of RAM that is available on the core
        The fifth argument (idlepow)         is the average instantaneous power dissipated by an idle node in W.
        The sixth argument (freq_dep_specs)  is the variable that contains all the frequency-dependednt specifications that are be measured. Starting with the maximum 
                                                as the first element which will be the default. Here it is condensed to a dictionary of the frequencies (keys) in GHz 
                                                a machine can run at, (value) paired with a tuple that corresponds to the average* instantaneous power dissipated in W,
                                                and the the score for the machine when HEPSCORE v1.5 + Ver 2.2 of the HEPScore suite is run at max frequency.   
                                                * = The <75%-95%> - the average of all points between and incuding the 75th and 95th percentiles of power-arranged data
                                                Format: {frequency_i:(power_i,HEPScore_i), frequency_j:(power_j,HEPScore_j), [...]}
        OLD || The seventh argument (duration)      is the time in seconds it takes for a node to run HEPSCORE v1.5 + Ver 2.2 of the HEPScore suite on max frequency.                                                                                             
        '''
        self._simulation_time = simulation_time
        self._hostname = hostname
        self._number_of_threads = threads
        self._number_of_cores = self._number_of_threads/2 # Differentiate for power consumption purposes.
        self._busy_cores = 0
        self._maximum_RAM = memory
        self._busy_RAM = 0
        self._jobs = []

        self._powerusage_idle = idlepower/3600 # Energy use (Needs to convert from hours to seconds)
        # Frequency-dependent specifications.
        self._frequencies = []
        self._powers_available = []
        self._HEPScores = []

        for freqs in sorted(freq_dep_specs.keys(), reverse=True): 
            (power, HEPScore) = freq_dep_specs[freqs]
            self._frequencies.append(freqs)
            self._powers_available.append(power/3600)
            self._HEPScores.append(HEPScore)

        
        self._running_frequency = self._frequencies[0]
        self._previous_frequency = self._frequencies[0]
        
        self._max_HEPScore = self._HEPScores[0]

        self._powerusage_active = self._powers_available[0]   

        # Performance multipliers
        self._fixed_duration_multiplier = (1939.60)/(self._max_HEPScore) # 1 The relative HEPScore on this machine running a standard benchmark compared to 2*AMD Milano (d22) node at max frequency.
        self._dynamic_duration_multiplier = 1 # For use of relative duration scaling when clocking up/down nodes.

        # Node descriptors
        self._system = "Arthur C Clarke"
        self._cpu = "HAL 9000"
        self._year = "3001"

        # Handlers
        self._job_started_handler = None
        self._job_finished_handler = None
    
    # -----------------
    # Getters
    # -----------------
    @property
    def cpu(self):
        return self._cpu  
    
    @property
    def hostname(self):
        return self._hostname
    
    @property
    def jobs(self):
        return self._jobs
    
    @property
    def system(self):
        return self._system
    
    @property
    def year(self):
        return self._year

    @property
    def busy_RAM(self):
        return self._busy_RAM
    @property
    def max_RAM(self):
        return self._maximum_RAM
    
    @property
    def busy_cores(self):
        return self._busy_cores
    @property
    def number_of_cores(self): # People care about the number of places that run jobs so they will interchange cores with threads. 
        return self._number_of_threads

    @property
    def powerusage_active(self):
        return self._powerusage_active
    @property
    def powers_available(self):
        return self._powers_available
    @property
    def powerusage_idle(self):
        return self._powerusage_idle
    
    @property
    def frequencies_available(self):
        return self._frequencies
    @property
    def running_frequency(self):
        return self._running_frequency

    @property
    def HEPScore_vs_frequency(self):
        return self._HEPScores
    @property
    def max_HEPScore(self):
        return self._max_HEPScore

    # -----------------
    # Setters
    # -----------------
    @hostname.setter
    def hostname(self, value):
        if isinstance(value, str) == False: 
            raise TypeError("The type of hostname should be `string` ")
        self._hostname = value

    @powerusage_idle.setter
    def powerusage_idle(self,value):
        if value > self._powerusage_active:
            raise ValueError("An active power consumption less than an idle power is not possible.")  
        self._powerusage_idle = value

    @powerusage_active.setter
    def powerusage_active(self,value):
        if value < self._powerusage_idle:
            raise ValueError("An active power consumption less than an idle power is not possible.")   
        self._powerusage_active = value

    @busy_RAM.setter
    def busy_RAM(self,value):
        if value > self._maximum_RAM:
            raise ValueError("Cannot allocate more RAM than is available on the machine.")  
        self._busy_RAM = value

    @running_frequency.setter
    def running_frequency(self,value):
        if value not in self.frequencies_available:
            raise ValueError("The machine cannot be set to run at this frequency.")  
        self._previous_frequency = self.running_frequency
        self._running_frequency = value   
    # -----------------
    # Functions
    # -----------------
    def set_datalogger_handlers(self, job_started, job_finished):
        self._job_started_handler = job_started
        self._job_finished_handler = job_finished


    def is_awaiting_jobs(self):
        return self.get_free_core_count() > 0

    def get_free_core_count(self):
        return self._number_of_threads - self._busy_cores
    
    def get_memory_available(self):
        return self._maximum_RAM - self._busy_RAM
  
    def can_schedule_job(self, job):
        if job.cores_req > self.get_free_core_count(): return False
        if job.memory_req > self.get_memory_available(): return False
        return True
     
    def start_job(self, job):
        job.start_time = self._simulation_time.get_current_datetime()
        # Adjust sampled duration according to worker node performance
        job.duration *=  self._fixed_duration_multiplier 
        # Adjust end times based on how the nodes are running
        freqindex = self.frequencies_available.index(self._running_frequency)
        currentHEPScore = self._HEPScores[freqindex]
        job.duration *= self.max_HEPScore/currentHEPScore


        self._job_started_handler(job, self)
        self._jobs.append(job)
        self._busy_cores += job.cores_req
        self._busy_RAM   += job.memory_req*job.cores_req
            

    def timestep_power_dissipated(self):
        # Outputs the amount of power used by a machine in a timestep in kWh. 
        # Assume that machines always use the idle power amount but power dissipated scales linearly with number of cores used to the maximum. 
        baseusage = self._powerusage_idle
        maxusage  = self._powerusage_active
        physicalcores = self._number_of_cores
        coresactive = self._busy_cores # Actually the number of threads active in a HT system.
        
        # In a HT system, each core runs two threads and the load is usually balances, so to a good approximation, the max energy output is when
        # half the threads are in use, one running on every core. A core roughly will not consume more power by running 2 threads instead of 1.
        scaling = coresactive/physicalcores 
        if scaling > 1: scaling = 1

        inst_pow_disp = maxusage * scaling   
        if inst_pow_disp < baseusage: inst_pow_disp = baseusage # Can't expend less power than the idle.
        
        inst_pow_disp_timestep = inst_pow_disp * self._simulation_time.get_timestep() # Scale up from power per second to power per timestep.
        inst_pow_disp_timestep = inst_pow_disp_timestep/1000 # Convert from Wh to kWh.

        return inst_pow_disp_timestep
    

    def change_clock_speed(self, clockspeed):
        # Function to change the clock speed or frequency of a node - unit is GHz
        self.running_frequency = clockspeed
        
        for job in self._jobs:
            # Change the amount of time left on all jobs running on the node
            timeLeftOnJob  = job.end_time - self._simulation_time.get_current_datetime()
            newJobDuration = timeLeftOnJob * self._dynamic_duration_multiplier
            job.end_time = self._simulation_time.get_current_datetime() + newJobDuration
            

    def clock_down(self):
        # Function to decrease the frequency of a node by one available frequency-step.
        freqindex = self.frequencies_available.index(self._running_frequency)
        try: 
            # Change the power setting according to the frequency
            self._powerusage_active = self.powers_available[freqindex+1]
            # Alter the length of a job ratio of the HEPScore in the frequency you are moving to w.r.t the one you are moving from
            self._dynamic_duration_multiplier = self._HEPScores[freqindex]/self._HEPScores[freqindex+1]

            self.change_clock_speed(self.frequencies_available[freqindex+1])
        except IndexError:
            print(f"This machine, {self.hostname}, is already running at its lowest frequency: {self.frequencies_available[freqindex]} GHz.")

    def clock_minimum(self):
            # Function to decrease the frequency of a node to the lowest available frequency-setting.
            freqindex = self.frequencies_available.index(self._running_frequency)

            # Change the power setting to the lowest frequency
            self._powerusage_active = self.powers_available[-1]
            # Alter the length of a job ratio of the HEPScore in the frequency you are moving to w.r.t the one you are moving from
            self._dynamic_duration_multiplier = self._HEPScores[freqindex]/self._HEPScores[-1]

            self.change_clock_speed(self.frequencies_available[-1])

    def clock_up(self):    
        # Function to increase the frequency of a node by one available frequency-step.
        freqindex = self.frequencies_available.index(self._running_frequency)
        if freqindex-1 >= 0:
            # Change the power setting according to the frequency
            self._powerusage_active = self.powers_available[freqindex-1]
            # Change the length of a job by the job-extension-factor in the frequency you are moving from 
            self._dynamic_duration_multiplier = self._HEPScores[freqindex]/self._HEPScores[freqindex-1]

            self.change_clock_speed(self.frequencies_available[freqindex-1])
        else:
            print(f"This machine, {self.hostname}, is already running at its maximum frequency: {self.frequencies_available[freqindex]} GHz.")

    def clock_maximum(self):
            # Function to decrease the frequency of a node to the highest available frequency-setting.
            freqindex = self.frequencies_available.index(self._running_frequency)

            # Change the power setting to the highest stable frequency
            self._powerusage_active = self.powers_available[0]
            # Alter the length of a job ratio of the HEPScore in the frequency you are moving to w.r.t the one you are moving from
            self._dynamic_duration_multiplier = self._HEPScores[freqindex]/self._HEPScores[0]

            self.change_clock_speed(self.frequencies_available[0])
  
    #### @lp.profile
    def update(self):
        remaining_jobs = []
        finished_jobs = []

        for job in self._jobs:
            # Has the job finished?
            if job.end_time <= self._simulation_time.get_current_datetime():
                if job not in finished_jobs:
                    job.duration = (job.end_time - job.start_time).seconds # need to update the duration of the job if it has been edited due to clockdowns
                    self._job_finished_handler(job, self)
                    finished_jobs.append(job)
                    self._busy_RAM   -= job.memory_req*job.cores_req # Need to free up the memory now it is no longer being used.
                    self._busy_cores -= job.cores_req  # Need to free up the cores now they are no longer being used.
            else:
                remaining_jobs.append(job)

        self._jobs = remaining_jobs

