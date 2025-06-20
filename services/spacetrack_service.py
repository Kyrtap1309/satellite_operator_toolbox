from datetime import datetime, timedelta
from typing import Any, Optional

import requests

from config import Config
from models.satellite import TLEData
from utils.logging_config import get_logger


class SpaceTrackService:
    """Service for interacting with Space-Track.org API."""

    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.SPACETRACK_BASE_URL
        self.session: Optional[requests.Session] = None
        self.logger = get_logger(__name__)

    def authenticate(self) -> bool:
        """Authenticate with Space-Track.org."""
        if not self.config.SPACETRACK_USERNAME or not self.config.SPACETRACK_PASSWORD:
            self.logger.error("Space-Track credentials not found")
            return False

        self.logger.info(f"Authenticating with Space-Track as: {self.config.SPACETRACK_USERNAME}")

        try:
            self.session = requests.Session()
            login_url = f"{self.base_url}/ajaxauth/login"
            login_data = {
                "identity": self.config.SPACETRACK_USERNAME,
                "password": self.config.SPACETRACK_PASSWORD,
            }

            response = self.session.post(login_url, data=login_data, timeout=30)
            response.raise_for_status()

            # Test authentication
            test_url = f"{self.base_url}/basicspacedata/query/class/tle_latest/NORAD_CAT_ID/25544/limit/1/format/json"
            test_response = self.session.get(test_url, timeout=30)

            success = test_response.status_code == 200 and test_response.text.strip() != "[]"
            if success:
                self.logger.info("Space-Track authentication successful")
            else:
                self.logger.error(f"Authentication test failed: {test_response.status_code}")

            return success

        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            if self.session:
                self.session.close()
                self.session = None
            return False

    def _ensure_authenticated(self) -> requests.Session:
        """Ensure we have an authenticated session."""
        if self.session is None:
            if not self.authenticate():
                raise Exception("Authentication failed")

        if self.session is None:
            raise Exception("Failed to create session")

        return self.session

    def fetch_tle_history(self, norad_id: str, days_back: int = 30) -> list[TLEData]:
        """Fetch historical TLE data."""

        session = self._ensure_authenticated()

        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")

            query_url = (
                f"{self.base_url}/basicspacedata/query/class/tle/"
                f"NORAD_CAT_ID/{norad_id}/"
                f"EPOCH/{start_date_str}--{end_date_str}/"
                f"orderby/TLE_LINE1%20desc/"
                f"format/json"
            )

            response = session.get(query_url, timeout=30)
            response.raise_for_status()
            data = response.json()

            if not data:
                return []

            tle_list = self._parse_tle_history(data)

            return tle_list

        except Exception as e:
            self.logger.error(f"Failed to fetch TLE history: {e}")
            raise

    def get_latest_tle_age(self, norad_id: str) -> dict[str, Any]:
        """Get age information for latest TLE."""

        session = self._ensure_authenticated()

        try:
            query_url = f"{self.base_url}/basicspacedata/query/class/tle_latest/NORAD_CAT_ID/{norad_id}/format/json"

            response = session.get(query_url, timeout=30)
            response.raise_for_status()
            data = response.json()

            if not data:
                raise Exception("No TLE found")

            age_info = self._calculate_tle_age(data[0])

            return age_info

        except Exception as e:
            self.logger.error(f"Failed to get TLE age: {e}")
            raise

    def _parse_tle_history(self, data: list[dict[str, Any]]) -> list[TLEData]:
        """Parse TLE history data."""
        tle_list = []

        for entry in data:
            try:
                mean_motion = self._safe_float(entry.get("MEAN_MOTION"))
                period_minutes = round(1440 / mean_motion, 2) if mean_motion > 0 else None

                # Ensure TLE lines are properly formatted
                tle_line1 = entry.get("TLE_LINE1", "").strip()
                tle_line2 = entry.get("TLE_LINE2", "").strip()

                # Validate TLE line lengths (should be exactly 69 characters)
                if len(tle_line1) != 69:
                    self.logger.warning(f"TLE Line 1 has incorrect length: {len(tle_line1)} (expected 69)")
                if len(tle_line2) != 69:
                    self.logger.warning(f"TLE Line 2 has incorrect length: {len(tle_line2)} (expected 69)")

                tle_data = TLEData(
                    norad_id=entry.get("NORAD_CAT_ID", ""),
                    satellite_name=entry.get("OBJECT_NAME", ""),
                    tle_line1=tle_line1,
                    tle_line2=tle_line2,
                    epoch=entry.get("EPOCH", ""),
                    mean_motion=mean_motion,
                    eccentricity=self._safe_float(entry.get("ECCENTRICITY")),
                    inclination=self._safe_float(entry.get("INCLINATION")),
                    ra_of_asc_node=self._safe_float(entry.get("RA_OF_ASC_NODE")),
                    arg_of_pericenter=self._safe_float(entry.get("ARG_OF_PERICENTER")),
                    mean_anomaly=self._safe_float(entry.get("MEAN_ANOMALY")),
                    classification=entry.get("CLASSIFICATION_TYPE"),
                    intl_designator=entry.get("INTLDES"),
                    element_set_no=self._safe_int(entry.get("ELEMENT_SET_NO")),
                    rev_at_epoch=self._safe_int(entry.get("REV_AT_EPOCH")),
                    bstar=entry.get("BSTAR"),
                    mean_motion_dot=entry.get("MEAN_MOTION_DOT"),
                    mean_motion_ddot=entry.get("MEAN_MOTION_DDOT"),
                    period_minutes=period_minutes,
                )
                tle_list.append(tle_data)

            except Exception as e:
                self.logger.error(f"Error parsing TLE entry: {e}")
                continue

        return tle_list

    def _calculate_tle_age(self, tle_data: dict[str, Any]) -> dict[str, Any]:
        """Calculate TLE age information."""
        epoch_str = tle_data.get("EPOCH")
        if not epoch_str:
            raise Exception("No epoch data")

        epoch_dt = self._parse_epoch_date(epoch_str)
        age_days = (datetime.now() - epoch_dt).days

        return {
            "epoch": epoch_str,
            "age_days": age_days,
            "is_fresh": age_days < 7,
            "warning": "TLE is outdated" if age_days > 14 else None,
        }

    def _parse_epoch_date(self, epoch_str: str) -> datetime:
        """Parse epoch date with multiple format support."""
        date_formats = [
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
        ]

        for date_format in date_formats:
            try:
                return datetime.strptime(epoch_str, date_format)
            except ValueError:
                continue

        raise ValueError(f"Could not parse epoch: {epoch_str}")

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        """Safely convert value to float."""
        try:
            return float(value) if value is not None else default
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        """Safely convert value to int."""
        try:
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default

    def __del__(self) -> None:
        """Clean up session."""
        if self.session:
            self.session.close()
