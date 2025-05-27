import logging
import os
from logging.handlers import RotatingFileHandler

from config import Config


def setup_logging(app, config: Config):
    """Configure application logging."""
    if not app.debug:
        # Production logging
        if not os.path.exists(config.LOG_DIR):
            os.mkdir(config.LOG_DIR)

        log_file_path = os.path.join(config.LOG_DIR, config.LOG_FILE)
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=config.LOG_MAX_BYTES,
            backupCount=config.LOG_BACKUP_COUNT,
        )
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
            )
        )
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info("Satellite Operator Application startup")
    else:
        # Development logging
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        console_handler.setLevel(logging.DEBUG)
        app.logger.addHandler(console_handler)
        app.logger.setLevel(logging.DEBUG)
        app.logger.info("Satellite Operator Application startup (DEBUG mode)")
