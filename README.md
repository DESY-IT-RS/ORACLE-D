# The ORACLE-D Framework

## Description
The Optimised Resource Analysis and Carbon Legacy Estimator for Data centres (ORACLE-D) Framework is a framework for simulating different types of compute nodes, seeing how they deal with incoming jobs, and how much power consumed/carbon emitted in doing so. The initial idea was to use this to investigate how energy consumption and/or carbon usage can be reduced an average Grid computing site. This software was written in Python3

## Project status
Version 0.1.0 has been presented at the 2024 HEPiX Spring Workshop in Paris.   

Release Date | Version Number | Release Name | DOI link |
| :------------: | :------------: | :------------: | :------: |
| ------     | LATEST |  ------        | <a href="https://doi.org/10.5281/zenodo.20720295"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.20720295.svg" alt="LATEST"></a> |
| 2026-07-17 | 1.1.0  | Betelgeuse     | <a href="https://doi.org/10.5281/zenodo.21416697"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.21416697.svg" alt="v1.1.0"></a> |
| 2026-03-31* | 1.0.0  | Antares       | <a href="https://doi.org/10.5281/zenodo.20720296"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.20720296.svg" alt="v1.0.0"></a> |

\* Due to a technical issue, the DOI for Antares was generated on the 2026-06-17, but the code for the release was frozen on 2026-03-31, and the DOI generated on that date for this repository no longer works. 

## Current Functionality
The simulation framework is designed to simulate the amount of energy and carbon used* when a computing site[1] performing work[2] is run in different ways[3]. The simulation is modular so [1],[2] and[3] are easily editable. 

\* All the nodes that make up the computing site output the amount of energy they have used every time-step (10 minutes), this is also multiplied by the carbon intensity of the UK grid to estimate the carbon emissions per time-step.

[1] A computing site is made up solely of a specified type(s) and number(s) of compute nodes defined in src/cluster/WorkerNode.py which run work.

[2] The work that the nodes run is made up jobs that are specified in src/jobs/VOJobFactory.py, and are inserted into the simulation either at the beginning of the simulation or at fixed durations throughout the simulation in src/jobs/JobScheduler.py.

[3] The different saving policies that the simulation can be run with are specified via a setting in config.json. This policy changes the frequency the nodes are run at and at what times of day this is done. Current running options are

| Running Flag  | Description |
| :------------: | :------ |
| None          |  Run the nodes as standard  |
| cd            |  Runs all the nodes clocked down one frequency step from the reported maximum frequency for the entire duration of the simulation    | 
| cdcd          |  Runs all the nodes clocked down two frequency steps from the reported maximum frequency for the entire duration of the simulation      |
| cd1721        |  Runs all the nodes clocked down one frequency step from the reported maximum frequency only between the hours of 5pm and 9pm  |
| cdcd1721      |  Runs all the nodes clocked down two frequency steps from the reported maximum frequency only between the hours of 5pm and 9pm   |
| highforecast  |  Runs all the nodes clocked down one frequency step from the reported maximum frequency only when the forecasted usage is high (> 400gCO2e/kWh)   |

The Simulation has two encoded end conditions
  1) All the jobs sent to the cluster have been completed
  2) The amount of time in seconds specified with self._simulation_length has passed

**Outputs**
-  Number of jobs started and finished. 
-  Total and Peak-time (17h-21h) Estimated Energy used in kWh.
-  Total and Peak-time Estimated Carbon (C02e) used in kg.
-  Total and average CPU duration.
-  Total real-time and simulated-time passed.
-  Average occupancy of the cluster

### Package Dependencies
ORACLE-D package metadata, supported Python version, runtime dependencies, and optional dependency groups are defined in `pyproject.toml`. The `requirements.txt` file references that project metadata for pip-based environment setup.

For those that use pip and venv to manage environment, you can run these commands that create a virtual environment called 'venv' to hold the environment needed for the project. 
```
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

### Running tests
The automated tests live under `tests/` and are run with `pytest`. They use the
small deterministic input files in `tests/fixtures/` rather than the full
default data set, so they are intended to be quick integration checks.

To install the test dependencies and run the full suite:
```
python3 -m pip install -e ".[test]"
python3 -m pytest
```

The integration tests currently check that:
- cluster inventory and frequency CSV files can be loaded into worker nodes;
- malformed or incomplete CSV data raises an error with `strict` enabled and is logged and skipped otherwise;
- `src/Main.py --config ...` accepts an explicit configuration file;
- a minimal GridPP simulation completes and writes its run directory outputs;
- the generated `summary.json` contains the expected metrics and preserved simulation parameters;
- each savings policy (`cd`, `cdcd`, `cd1721`, `cdcd1721`, `highforecast`) produces the exactly expected total and peak-time energy and carbon values;
- jobs from `regular_incoming_mix` are submitted at the configured interval and started when capacity allows;
- optionally, the standard `config.json` run agrees with the reference output in `tests/fixtures/default/logs/runs/test/summary.json`, ignoring only wall-clock runtime fields.

A short description of every individual test is kept in `tests/README.md`.

For a faster targeted run while working on the simulation path, use:
```
python3 -m pytest tests/integration
```
The tests create temporary run directories through pytest fixtures, so they should not write new output into the repository's normal `logs/runs/` directory. The default-config reference test is optional because it is slower. It uses fixture copies of the default config, default cluster CSVs, carbon-intensity CSV, and reference output under `tests/fixtures/default/`, then writes its new run output to a pytest temporary directory. To include it, set:
```
ORACLE_D_RUN_DEFAULT_REFERENCE_TEST=1 python3 -m pytest tests/integration/test_default_config_reference.py
```

That test runs the same command as the first-run smoke test below,
`python3 src/Main.py`, with the fixture copy of `config.json`, and compares the
generated `summary.json` to
`tests/fixtures/default/logs/runs/test/summary.json`.

## Getting started with the first run
To run this simulation in this folder type the command:
```
python3 src/Main.py
```
By default, this reads `config.json` from the repository root. To run with a
different configuration file, pass it explicitly:
```
python3 src/Main.py --config path/to/config.json
```
The default running mode is to run 50,000 'GridPP' jobs on the default DESY Grid compute cluster without any special running conditions at medium verbosity. This could run for a couple of minutes and produce a log output, and the folder logs/runs/[DATE]_RF20PMTest-50000GridPP-Base with the summary of the output. The information of grid carbon intensity is taken from data/de_carbon_Intensity_2024_15min.csv. This can be compared to the folder that exists already in the folder which takes the same job mix started at the same time. This is equivalent to the default reference test described in the previous section.


## Configuration
The simulation is configured via a JSON config file. The default is `config.json` in the repository root, and another file can be selected with `--config`. In there, all relevant parameters are specified. They are split into several sections dealing with the different parts of the code.

### Simulation
The parameters that can be changed for the simulation include:

| Variables to edit  | Description |
| :------------: | :------ |
| desiredStartTime          | The time at which the simulation starts. Leaving this black defaults to clock time  |
| simulation_length   | The maximum duration that the will simulation will run for in seconds | 
| timestep   | The timestep the simulation does in between each update in seconds | 
| savings_policy   | The savings policy specified in an earlier section. The options are "None", "cd", "cdcd", "cd1721", "cdcd1721", and "highforecast". | 

### carbon_intensity
The parameters that define information on the carbon intensity. They include:

| Variables to edit  | Description |
| :------------: | :------ |
| folder          | The folder where the carbon intensity data is stored  |
| filename   | The filename of the carbon intensity data | 
| high_CI_threshold   | The threshold of what is considered a high carbon intensity in gCO2e/kWh | 

### jobs
In this part of the config, the type of jobs that the simpulation will run are specified. The relevant parameters are:

| Variables to edit  | Description |
| :------------: | :------ |
| initial_mix          | The initial mix of jobs submitted to the cluster. The format is a dictionary with the type of jobs as key and the number as value. Currently implemented are the jobtypes "ATLAS", "LHCb" and "GridPP". With any other name, a basic job will be run. |
| regular_incoming_mix   | A mix of jobs that gets submitted at regular intervals. The format is the same as initial_mix. If left empty, no jobs will be refilled. | 
| incoming_timestep   | The timestep between job submissions | 

### output
This part controls how much information is written to the logfile in the `logs/` directory.

| Variables to edit  | Description |
| :------------: | :------ |
| verbosity | Controls INFO-level logging detail. Valid values are `"low"`, `"medium"`, and `"high"`. |
| debug | Controls the logging level. If set to true, debug messages are logged alongside information, warnings and errors. |
| log_dir | Optional. Directory where per-run log folders are written. Defaults to `logs/runs`. |
| run_label | Optional. Human-readable label added to the run folder name. If omitted, the label is generated from the number of initial jobs and the savings policy. |

Each simulation run creates a folder named like `YYYY-MM-DD_HH-MM-SS_<run-label>` under `logs/runs/`. The folder contains `simulation.log`, `summary.txt`, `summary.json`, `parameters.txt`, and a copy of the run `config.json`.
The `summary.json` file contains both the simulation parameters and the final summary metrics for machine-readable comparisons between runs.

Verbosity behavior:
- `low`: only high-level lifecycle messages (for example simulation creation) are logged.
- `medium`: includes major progress messages (for example loading data and simulation end-condition messages).
- `high`: includes the most detailed INFO logs, including per-job start/finish entries from the data logger.

If `output.verbosity` is not one of `low`, `medium`, or `high`, ORACLE-D logs a warning and defaults to `high`.

### cluster

The parameters for the cluster include:

| Variables to edit  | Description |
| :------------: | :------ |
| cluster_name          | The name of the cluster  |
| inventory_csv   | The csv file with the inventory file of the cluster | 
| frequency_csv   | The csv file with frequency dependence of the cluster | 
| strict   | Whether the program should terminate when an incomplete frequency dependence data entry is found or simply log and continue. | 

## Adding Extra Options
If you want to amend the measurements for each node or add different types of node not yet in the simulation. This needs to be done at the bottom of src/cluster/WorkerNode.py.

To add new machines you will need the following information:
- name
- number of (hyper)threads
- amount of memory available to the node
- the value of the power displaced when node is IDLE
- the value of the power displaced when the node is fully occupied with work at its maximum frequency value
- HEPScore value for the node at its maximum frequency value
- (optional) the value of the power displaced of a fully occupied node at its alternative frequency values
- (optional) the HEPScore value of a fully occupied node at its alternative frequency values


## Custom cluster makeup
While ORACLE-D is shipped with a demo cluster makeup, it is designed to be easily adapted to other datacentres. For that, two datafiles are required: the inventory and the frequency dependence. Both filenames should be specified in config.json.

The format of the file is a csv with the following columns:

| Header entry  | Description |
| :------------: | :------ |
| type | The name of the type of nodes  |
| subtype   | The name of the subtype of nodes. Allows for greater flexibility in naming convention. The full name will be type_subtype | 
| number_machines   | The number of machines in each subtype | 
| total_threads   | The number of threads per machine | 
| total_mem_in_Gb | The amount of memory per machine in Gb |
| power_min_60d | The minimal power the machine draws, i.e. the idle power |
| model | The model of the machine (optional) |
| cpu_model | The cpu of the machine (optional) | 
| installation_date | The installation date of the machine (optional) | 

The format of the frequency filename is: TODO


## Copyright and License
Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY and the University of Glasgow

Original Authors: Dwayne Spiteri and Gordon Stewart.

All code in the src/ directory and subsequent subdirectory structure is 
licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

## Contributors
Dwayne Spiteri, Gordon Stewart and Konrad Kockler


## Acknowledgements
The measurements used here to catagorise the different types of server come from running the [HEPScore23 benchmark](https://w3.hepix.org/benchmarking/how_to_run_HS23.html) on compute nodes.  For the server examples used in ORACLE-D these were taken by **Emanuele Simili** at the University of Glasgow in February 2024 and **Jan Hartmann** at DESY in May of 2025.

The carbon intensity data for the UK is taken from the [UK National Grid ESO](https://www.nationalgrideso.com/data-portal/national-carbon-intensity-forecast/national_carbon_intensity_forecast) interpolated to fill in gaps in the data and can be downloaded from [here](https://www.nationalgrideso.com/data-portal/national-carbon-intensity-forecast/national_carbon_intensity_forecast) and for Germany is taken from [Agorameter](https://www.agora-energiewende.de/daten-tools/agorameter) and [Green Grid Compass](https://www.greengrid-compass.eu/).

This code was partially written for the RF2.0 project that has received funding from the European Union’s Horizon Europe research and innovation programme under grant agreement No. 101131850 and from the Swiss State Secretariat for Education Research and Innovation (SERI). Parts of the testing suite were written with the help of codex.
