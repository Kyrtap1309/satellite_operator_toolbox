import os
from dataclasses import dataclass


@dataclass
class Config:
    # Satellite defaults
    SATELLITE_NAME: str = "Bluebon"
    SATELLITE_TLE_LINE1: str = ""
    SATELLITE_TLE_LINE2: str = ""

    # Ground stations
    STATION1_NAME: str = "Sweden"
    STATION1_LAT: float = 65.337
    STATION1_LON: float = 21.425
    STATION1_ELEV: float = 21.0

    STATION2_NAME: str = "Poland"
    STATION2_LAT: float = 51.097
    STATION2_LON: float = 17.069
    STATION2_ELEV: float = 116.0

    # Calculation parameters
    MIN_ELEVATION: float = 3.0

    # Space-Track API
    SPACETRACK_USERNAME: str = os.getenv("SPACETRACK_USERNAME", "")
    SPACETRACK_PASSWORD: str = os.getenv("SPACETRACK_PASSWORD", "")
    SPACETRACK_BASE_URL: str = "https://www.space-track.org"

    # CelesTrak API
    CELESTRAK_BASE_URL: str = "https://celestrak.org/NORAD/elements/gp.php"

    # Logging
    LOG_MAX_BYTES: int = 10240000  # 10MB
    LOG_BACKUP_COUNT: int = 10
    LOG_DIR: str = "logs"
    LOG_FILE: str = "satellite_app.log"
    LOG_LEVEL: str = os.getenv(
        "LOG_LEVEL", "INFO"
    )  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    CONSOLE_LOG_LEVEL: str = os.getenv("CONSOLE_LOG_LEVEL", "DEBUG")
    FILE_LOG_LEVEL: str = os.getenv("FILE_LOG_LEVEL", "INFO")

    # Flask
    FLASK_HOST: str = "0.0.0.0"
    FLASK_PORT: int = 5000
    FLASK_DEBUG: bool = True
