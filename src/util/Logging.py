# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY
#                     and the University of Glasgow
# For more information about rights and fair use please refer to src/Main.py.
# For full detailed and legal infomration please read the LICENSE and NOTICE
#    files in the main directory
# ===========================================================================

import datetime
import logging
import os
import re

VALID_VERBOSITY_LEVELS = ("low", "medium", "high")


def __get_fn_log(log_dir=None):
    if log_dir is not None:
        return os.path.join(log_dir, "simulation.log")

    dir_logs = os.path.join(os.getcwd(), "logs")
    if not os.path.exists(dir_logs):
        os.mkdir(dir_logs)
    tag = f"{datetime.datetime.now():%Y%m%d-%H%M}"
    return os.path.join(dir_logs, f"{tag}.log")


def get_logger():
    return logging.getLogger("CLUSTERSIM")


def configure_logger(logger, level=logging.INFO, log_dir=None):
    logger.setLevel(level)

    # Avoid duplicate lines if configure_logger() is called more than once.
    logger.handlers = []
    handler = logging.FileHandler(__get_fn_log(log_dir))
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s  %(levelname)s  [%(filename)s:%(funcName)s]  %(message)s"
        )
    )
    logger.addHandler(handler)


def create_run_directory(config):
    output_cfg = config.setdefault("output", {})
    base_dir = output_cfg.get("log_dir", os.path.join(os.getcwd(), "logs", "runs"))
    os.makedirs(base_dir, exist_ok=True)

    timestamp = f"{datetime.datetime.now():%Y-%m-%d_%H-%M-%S}"
    run_label = output_cfg.get("run_label", _default_run_label(config))
    run_dir = os.path.join(base_dir, f"{timestamp}_{_slugify(run_label)}")

    suffix = 1
    unique_run_dir = run_dir
    while os.path.exists(unique_run_dir):
        suffix += 1
        unique_run_dir = f"{run_dir}_{suffix}"

    os.makedirs(unique_run_dir)
    output_cfg["run_dir"] = unique_run_dir
    return unique_run_dir


def normalize_verbosity(raw_verbosity, default="high"):
    verbosity = str(raw_verbosity) if raw_verbosity is not None else default
    if verbosity not in VALID_VERBOSITY_LEVELS:
        return default
    return verbosity


def _default_run_label(config):
    initial_jobs = config.get("jobs", {}).get("initial_mix", {})
    total_jobs = sum(initial_jobs.values())
    policy = config.get("Simulation", {}).get("savings_policy", "unknown-policy")
    return f"{total_jobs}jobs_{policy}"


def _slugify(value):
    slug = re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_")
    return slug.lower() or "simulation"
