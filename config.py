import os
from dataclasses import dataclass


@dataclass
class Config:
    # Satellite defaults
    SATELLITE_NAME: str = "Bluebon"
    SATELLITE_TLE_LINE1: str = (
        "1 62688U 25009CH  25124.74930353  .00015765  00000+0  69252-3 0  9994"
    )
    SATELLITE_TLE_LINE2: str = (
        "2 62688  97.4284 205.7904 0001127  28.6595 331.4703 15.22003295 16668"
    )

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

    # Flask
    FLASK_HOST: str = "0.0.0.0"
    FLASK_PORT: int = 5000
    FLASK_DEBUG: bool = True
