"""Central logging configuration. Call configure_logging() once at
process startup (monitor.py does this first thing) - every other
module just does `logger = logging.getLogger(__name__)` at the top and
logs normally; it inherits this configuration automatically.

Logs go to both stdout (so `python monitor.py` run directly shows
output, and `journalctl -u marketplace-monitor -f` works when run
under systemd) and a rotating file under logs/, so you can look back
further than journald's retention policy keeps around.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "monitor.log")


def configure_logging(level=logging.INFO):
    os.makedirs(LOG_DIR, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5_000_000, backupCount=3)
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(stream_handler)
    root.addHandler(file_handler)

    # requests/urllib3 are noisy at DEBUG - keep them quieter unless
    # you're specifically debugging HTTP internals.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
