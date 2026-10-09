#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# ========================================================================
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY 
#                     and the University of Glasgow
# Authors: Dwayne Spiteri and Gordon Stewart.
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# The main repository houses LICENSE and NOTICE files for your infromation 
# ========================================================================

from simulation.Simulation import Simulation
from cluster.ClusterLoader import load_cluster_inventory
from util import Logging
import argparse
import json
import os
import logging


logger = Logging.get_logger()


def _default_config_path():
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_dir, 'config.json')


def main(config_path=None):
    if config_path is None:
        config_path = _default_config_path()

    with open(config_path) as f:
        config = json.load(f)


    inventory = load_cluster_inventory(
            config["cluster"]["inventory_csv"],
            config["cluster"]["frequency_csv"],
            cluster_name = config["cluster"]["cluster_name"],
            strict = config["cluster"]["strict"],
        )

    output_cfg = config.setdefault("output", {})
    verbosity_raw = output_cfg.get("verbosity")
    config["output"]["verbosity"] = Logging.normalize_verbosity(verbosity_raw)

    if config["output"].get("debug", False):
        logging_level = logging.DEBUG
    else:
        logging_level = logging.INFO

    run_dir = Logging.create_run_directory(config)
    with open(os.path.join(run_dir, 'config.json'), 'w') as outfile:
        json.dump(config, outfile, indent=4)
        outfile.write('\n')

    Logging.configure_logger(logger, logging_level, run_dir)
    logger.info(f'Writing run output to {run_dir}')

    if verbosity_raw != config["output"]["verbosity"]:
        logger.warning(f"Invalid verbosity value '{verbosity_raw}', defaulting to 'high'")

    sim = Simulation(config, inventory)

    sim.start()
    #sim2 = Simulation('eveningclock') # Clock down the node at 5pm and up at 9pm
    #sim2.start()


def _parse_args():
    parser = argparse.ArgumentParser(description='Run an ORACLE-D simulation.')
    parser.add_argument(
        '--config',
        default=None,
        help='Path to the simulation config JSON file. Defaults to the repository config.json.',
    )
    return parser.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    main(args.config)
