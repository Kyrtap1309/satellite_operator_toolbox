import logging
import os
from logging.handlers import RotatingFileHandler

from config import Config


def get_log_level(level_str: str) -> int:
    """Convert string log level to logging constant."""
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return level_map.get(level_str.upper(), logging.INFO)


def setup_logging(app, config: Config):
    """Configure application logging."""
    # Remove existing handlers to avoid duplicates
    app.logger.handlers.clear()
    logging.getLogger().handlers.clear()

    # Set root logger level
    root_logger = logging.getLogger()
    root_logger.setLevel(get_log_level(config.LOG_LEVEL))

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s [%(filename)s:%(lineno)d]"
    )
    simple_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Always add console handler for Docker
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(simple_formatter)
    console_handler.setLevel(get_log_level(config.CONSOLE_LOG_LEVEL))

    root_logger.addHandler(console_handler)
    app.logger.addHandler(console_handler)

    # File handler only if not in container or if explicitly enabled
    if not app.debug or os.getenv("FLASK_ENV") == "production":
        if not os.path.exists(config.LOG_DIR):
            os.mkdir(config.LOG_DIR)

        log_file_path = os.path.join(config.LOG_DIR, config.LOG_FILE)
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=config.LOG_MAX_BYTES,
            backupCount=config.LOG_BACKUP_COUNT,
        )
        file_handler.setFormatter(detailed_formatter)
        file_handler.setLevel(get_log_level(config.FILE_LOG_LEVEL))

        root_logger.addHandler(file_handler)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(get_log_level(config.FILE_LOG_LEVEL))
        app.logger.info("Satellite Operator Application startup (PRODUCTION mode)")
    else:
        app.logger.setLevel(get_log_level(config.CONSOLE_LOG_LEVEL))
        app.logger.info("Satellite Operator Application startup (DEBUG mode)")

    # Configure specific loggers
    configure_module_loggers(config)


def configure_module_loggers(config: Config):
    """Configure logging for specific modules."""
    # Set logging level for requests library to reduce noise
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Configure service loggers
    service_loggers = [
        "services.celestrak_service",
        "services.spacetrack_service",
        "services.satellite_service",
    ]

    for logger_name in service_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(get_log_level(config.LOG_LEVEL))


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger for a module."""
    return logging.getLogger(name)
