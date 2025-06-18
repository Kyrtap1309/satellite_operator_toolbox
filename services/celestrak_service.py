from typing import Any

import requests

from config import Config
from models.satellite import TLEData
from utils.logging_config import get_logger

# Constants
TLE_FORMAT_LINE_COUNT = 3  # Satellite name + TLE line 1 + TLE line 2


class CelestrakService:
    """Service for interacting with CelesTrak API."""

    def __init__(self, config: Config):
        self.config = config
        self.base_url = "https://celestrak.org/NORAD/elements/gp.php"
        self.logger = get_logger(__name__)

    def fetch_current_tle(self, norad_id: str) -> TLEData:
        """Fetch current TLE data from CelesTrak."""

        try:
            self.logger.info(f"Fetching TLE data from CelesTrak for NORAD ID: {norad_id}")

            # Fetch both JSON and TLE format data
            json_data = self._fetch_json_data(norad_id)
            tle_lines = self._fetch_tle_lines(norad_id)

            # Combine data from both sources
            tle_data = self._combine_tle_data(json_data, tle_lines)

            self.logger.info(f"Successfully fetched TLE data for NORAD ID: {norad_id}")
            return tle_data

        except Exception as e:
            self.logger.error(f"Failed to fetch TLE from CelesTrak for NORAD ID {norad_id}: {e}")
            raise

    def _fetch_json_data(self, norad_id: str) -> Any:
        """Fetch JSON formatted orbital data."""
        json_url = f"{self.base_url}?CATNR={norad_id}&FORMAT=json"
        self.logger.debug(f"Fetching JSON data from: {json_url}")

        response = requests.get(json_url, timeout=10)
        response.raise_for_status()

        data = response.json()
        if not data:
            raise Exception(f"No JSON data found for NORAD ID: {norad_id}")

        return data[0]

    def _fetch_tle_lines(self, norad_id: str) -> dict[str, str]:
        """Fetch TLE format lines."""
        tle_url = f"{self.base_url}?CATNR={norad_id}&FORMAT=TLE"
        self.logger.debug(f"Fetching TLE lines from: {tle_url}")

        response = requests.get(tle_url, timeout=10)
        response.raise_for_status()

        tle_data = response.text.strip()
        if not tle_data:
            raise Exception(f"No TLE data found for NORAD ID: {norad_id}")

        lines = tle_data.split("\n")
        if len(lines) < TLE_FORMAT_LINE_COUNT:
            raise Exception("Invalid TLE format received")

        result = {
            "satellite_name": lines[0].strip(),
            "tle_line1": lines[1].strip(),
            "tle_line2": lines[2].strip(),
        }

        self.logger.debug(f"Successfully fetched TLE lines for: {result['satellite_name']}")
        return result

    def _combine_tle_data(self, json_data: dict[str, Any], tle_lines: dict[str, str]) -> TLEData:
        """Combine JSON and TLE line data."""
        period_minutes = None
        if json_data.get("MEAN_MOTION"):
            period_minutes = round(1440 / float(json_data["MEAN_MOTION"]), 2)

        return TLEData(
            norad_id=json_data.get("NORAD_CAT_ID", ""),
            satellite_name=tle_lines["satellite_name"],
            tle_line1=tle_lines["tle_line1"],
            tle_line2=tle_lines["tle_line2"],
            epoch=json_data.get("EPOCH", ""),
            mean_motion=float(json_data.get("MEAN_MOTION", 0)),
            eccentricity=float(json_data.get("ECCENTRICITY", 0)),
            inclination=float(json_data.get("INCLINATION", 0)),
            ra_of_asc_node=float(json_data.get("RA_OF_ASC_NODE", 0)),
            arg_of_pericenter=float(json_data.get("ARG_OF_PERICENTER", 0)),
            mean_anomaly=float(json_data.get("MEAN_ANOMALY", 0)),
            classification=json_data.get("CLASSIFICATION_TYPE"),
            intl_designator=json_data.get("INTLDES"),
            element_set_no=json_data.get("ELEMENT_SET_NO"),
            rev_at_epoch=json_data.get("REV_AT_EPOCH"),
            bstar=json_data.get("BSTAR"),
            mean_motion_dot=json_data.get("MEAN_MOTION_DOT"),
            mean_motion_ddot=json_data.get("MEAN_MOTION_DDOT"),
            period_minutes=period_minutes,
        )
