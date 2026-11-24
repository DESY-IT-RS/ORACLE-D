import logging

import pytest

from util import Logging


@pytest.mark.parametrize(
    "output, level",
    [
        ({"verbosity": "low"}, logging.INFO),
        ({"verbosity": "medium"}, Logging.EVENT),
        ({"verbosity": "high"}, Logging.DETAIL),
        ({"verbosity": "debug"}, logging.DEBUG),
        ({"verbosity": "low", "debug": True}, logging.DEBUG),
        ({"verbosity": "loud"}, Logging.DETAIL),  # invalid falls back to high
        ({}, Logging.DETAIL),
    ],
)
def test_log_level_follows_verbosity_and_debug(output, level):
    assert Logging.log_level(output) == level


def test_levels_sit_between_info_and_debug():
    assert logging.DEBUG < Logging.DETAIL < Logging.EVENT < logging.INFO
    assert logging.getLevelName(Logging.EVENT) == "EVENT"
    assert logging.getLevelName(Logging.DETAIL) == "DETAIL"


def test_console_never_shows_per_job_lines(tmp_path, capsys):
    logger = logging.getLogger("CLUSTERSIM.test_console")
    Logging.configure_logger(logger, Logging.DETAIL, tmp_path)

    logger.info("lifecycle")
    logger.log(Logging.EVENT, "event")
    logger.log(Logging.DETAIL, "job line")
    for handler in logger.handlers:
        handler.close()

    console = capsys.readouterr().out
    log_file = (tmp_path / "simulation.log").read_text()
    assert console == "lifecycle\nevent\n"
    assert "DETAIL" in log_file and "job line" in log_file
