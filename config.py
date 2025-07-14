import os
from dataclasses import dataclass
from typing import Any

@dataclass
class Config:
    # Satellite defaults
    SATELLITE_NAME: str = "Bluebon"
    SATELLITE_TLE_LINE1: str = ""
    SATELLITE_TLE_LINE2: str = ""

    DEFAULT_GROUND_STATIONS: list[dict[str, Any]] = None

    def __post_init__(self):
        if self.DEFAULT_GROUND_STATIONS is None:
            self.DEFAULT_GROUND_STATIONS = [
                {
                    "name": "Sweden",
                    "latitude": 65.337,
                    "longitude": 21.425,
                    "elevation": 21.0
                },
                {
                    "name": "Wroclaw",
                    "latitude": 51.097,
                    "longitude": 17.069,
                    "elevation": 116.0
                },
                {
                    "name": "Pretoria",
                    "latitude": -25.746,
                    "longitude": 28.188,
                    "elevation": 1200.0
                }
                
            ]

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
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    CONSOLE_LOG_LEVEL: str = os.getenv("CONSOLE_LOG_LEVEL", "DEBUG")
    FILE_LOG_LEVEL: str = os.getenv("FILE_LOG_LEVEL", "INFO")

    # Flask
    FLASK_HOST: str = os.getenv("FLASK_HOST", "127.0.0.1")
    FLASK_PORT: int = 5000
    FLASK_DEBUG: bool = True
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")

    # Database configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://satellite_user:password@localhost:5432/satellite_db")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "satellite_password")
