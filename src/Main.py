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

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from simulation.Simulation import Simulation
from util import Logging, Verification

logger = Logging.get_logger()


def _default_config_path():
    return Path(__file__).parent.parent / "config.json"


def main(config_path=None, verify_only=False):
    if config_path is None:
        config_path = _default_config_path()

    try:
        with open(config_path) as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot read config file {config_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    # Check the whole config and its data files before anything is written.
    verification = Verification.verify_config(config)
    if not Verification.report(verification, config_path):
        sys.exit(1)
    if verify_only:
        print(f"Configuration check for {config_path} passed.")
        return

    # Fix a clock-time start once, so the checked carbon window is the simulated one.
    if config["Simulation"]["desired_starttime"] is None:
        config["Simulation"]["desired_starttime"] = verification.start_time

    output_cfg = config.setdefault("output", {})
    config["output"]["verbosity"] = Logging.normalize_verbosity(
        output_cfg.get("verbosity")
    )

    if config["output"].get("debug", False):
        logging_level = logging.DEBUG
    else:
        logging_level = logging.INFO

    run_dir = Logging.create_run_directory(config)
    with open(os.path.join(run_dir, "config.json"), "w") as outfile:
        json.dump(config, outfile, indent=4)
        outfile.write("\n")

    Logging.configure_logger(logger, logging_level, run_dir)
    logger.info(f"Writing run output to {run_dir}")

    for message in verification.warnings:
        logger.warning(message)

    sim = Simulation(
        config,
        verification.inventory,
        verification.worker_nodes,
        verification.carbon_data,
    )

    sim.start()
    # sim2 = Simulation('eveningclock') # Clock down the node at 5pm and up at 9pm
    # sim2.start()


def _parse_args():
    parser = argparse.ArgumentParser(description="Run an ORACLE-D simulation.")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to the simulation config JSON file. Defaults to the repository config.json.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only check the config and its cluster and carbon-intensity files, then exit.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(args.config, args.verify_only)
