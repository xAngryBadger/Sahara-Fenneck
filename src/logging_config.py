import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_log_path() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home() / ".sahara_fennec")
    root = Path(appdata) / "SaharaFennec"
    root.mkdir(parents=True, exist_ok=True)
    return root / "sahara_fennec.log"


def setup_logging(level: int = logging.INFO) -> None:
    log_path = get_log_path()
    handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger = logging.getLogger("src")
    root_logger.setLevel(level)
    if not root_logger.handlers:
        root_logger.addHandler(handler)
