import logging
from typing import Any

from models.satellite import TLEData
from services.satellite_service import SatelliteService

# Constants
TLE_LINE_LENGTH = 69  # Standard TLE line length


class TLEInputService:
    """Service for handling TLE input from various sources."""

    def __init__(self, satellite_service: SatelliteService):
        self.satellite_service = satellite_service
        self.logger = logging.getLogger(__name__)

    def get_tle_data(self, form_data: dict[str, Any]) -> TLEData:
        """Get TLE data from form based on input method."""
        input_method = form_data.get("input_method", "tle")

        if input_method == "norad":
            return self._get_tle_from_norad(form_data)
        else:
            return self._get_tle_from_form(form_data)

    def _get_tle_from_form(self, form_data: dict[str, Any]) -> TLEData:
        """Extract TLE data from manual form input."""
        satellite_name = form_data.get("tle_name", "Unknown Satellite")
        tle_line1 = form_data.get("tle_line1", "")
        tle_line2 = form_data.get("tle_line2", "")

        if not tle_line1 or not tle_line2:
            raise ValueError("TLE lines cannot be empty")

        # Basic validation
        if len(tle_line1) != TLE_LINE_LENGTH or len(tle_line2) != TLE_LINE_LENGTH:
            raise ValueError(f"TLE lines must be exactly {TLE_LINE_LENGTH} characters long")

        # Extract NORAD ID from TLE line 1
        try:
            norad_id = tle_line1[2:7].strip()
        except (IndexError, ValueError):
            norad_id = "00000"

        return TLEData(satellite_name=satellite_name, norad_id=norad_id, tle_line1=tle_line1, tle_line2=tle_line2)

    def _get_tle_from_norad(self, form_data: dict[str, Any]) -> TLEData:
        """Get TLE data from NORAD ID using satellite service."""
        norad_id = form_data.get("norad_id", "").strip()

        if not norad_id:
            raise ValueError("NORAD ID cannot be empty")

        try:
            tle_data = self.satellite_service.get_current_tle(norad_id)
            if not tle_data:
                raise ValueError(f"No TLE data found for NORAD ID: {norad_id}")
            return tle_data
        except Exception as e:
            self.logger.error(f"Error fetching TLE for NORAD ID {norad_id}: {e}")
            raise ValueError(f"Failed to fetch TLE data for NORAD ID {norad_id}: {e!s}") from e
