import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import settings

LOG_DIR = Path(__file__).parent / "logs"
FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(process: str) -> None:
    """Configure logging once per process (process="api" now, "worker" later).
    Logs go to the console and to logs/<process>.log; one file per process, because
    two processes rotating the same file would clash.
    Modules then log with logging.getLogger(__name__)."""
    LOG_DIR.mkdir(exist_ok=True)
    # Rotates at 5 MB and keeps 3 old files, so the folder never grows past ~20 MB
    file_handler = RotatingFileHandler(
        LOG_DIR / f"{process}.log", maxBytes=5_000_000, backupCount=3
    )
    file_handler.setFormatter(logging.Formatter(FORMAT))

    logging.basicConfig(level=settings.log_level, format=FORMAT)
    logging.getLogger().addHandler(file_handler)
    # Uvicorn's loggers don't pass records up to the root logger, so attach the file
    # to them directly: "uvicorn" holds crash tracebacks, "uvicorn.access" the requests.
    for name in ("uvicorn", "uvicorn.access"):
        logging.getLogger(name).addHandler(file_handler)
