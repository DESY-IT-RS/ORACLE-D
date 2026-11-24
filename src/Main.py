#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# ========================================================================
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY
#                     and the University of Glasgow
# Original Authors: Dwayne Spiteri and Gordon Stewart.
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
    verified = Verification.verify_config(config)
    # With --verify-only the report is the output, so it lists every passed check on stdout.
    if verify_only:
        if not Verification.report(
            verified, config_path, stream=sys.stdout, show_passed=True
        ):
            sys.exit(1)
        print(f"Configuration check for {config_path} passed.")
        return
    if not verified.ok:
        Verification.report(verified, config_path)
        sys.exit(1)

    # Fix a clock-time start once, so the checked carbon window is the simulated one.
    if config["Simulation"]["desired_starttime"] is None:
        config["Simulation"]["desired_starttime"] = verified.start_time

    output_cfg = config.setdefault("output", {})
    config["output"]["verbosity"] = Logging.normalize_verbosity(
        output_cfg.get("verbosity")
    )

    run_dir = Logging.create_run_directory(config)
    with open(os.path.join(run_dir, "config.json"), "w") as outfile:
        json.dump(config, outfile, indent=4)
        outfile.write("\n")

    Logging.configure_logger(logger, Logging.log_level(config["output"]), run_dir)
    logger.info("Writing run output to %s", run_dir)

    # Without errors, the warnings go through the logger: to the terminal and simulation.log.
    for message in verified.warnings:
        logger.warning(message)

    sim = Simulation(
        config,
        verified.inventory,
        verified.worker_nodes,
        verified.carbon_data,
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
