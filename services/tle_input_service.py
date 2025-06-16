from models.satellite import TLEData
from services.satellite_service import SatelliteService


class TLEInputService:
    """Service for handling TLE input methods."""

    def __init__(self, satellite_service: SatelliteService):
        self.satellite_service = satellite_service

    def get_tle_data(self, form_data: dict[str, str]) -> TLEData:
        """Get TLE data from form input (NORAD ID or manual TLE)."""
        input_method = form_data.get("input_method", "norad")

        if input_method == "norad":
            return self._get_tle_from_norad_id(form_data)
        else:
            return self._create_tle_from_manual_input(form_data)

    def _get_tle_from_norad_id(self, form_data: dict[str, str]) -> TLEData:
        """Fetch TLE from NORAD ID."""
        norad_id = form_data.get("norad_id")
        if not norad_id:
            raise ValueError("Please provide a NORAD ID")

        return self.satellite_service.get_current_tle(norad_id)

    def _create_tle_from_manual_input(self, form_data: dict[str, str]) -> TLEData:
        """Create TLE data from manual input."""
        tle_name = form_data["tle_name"]
        tle_line1 = form_data["tle_line1"]
        tle_line2 = form_data["tle_line2"]

        if not all([tle_name, tle_line1, tle_line2]):
            raise ValueError("Please provide complete TLE data")

        return TLEData(
            norad_id="",
            satellite_name=tle_name,
            tle_line1=tle_line1,
            tle_line2=tle_line2,
            epoch="",
            mean_motion=0.0,
            eccentricity=0.0,
            inclination=0.0,
            ra_of_asc_node=0.0,
            arg_of_pericenter=0.0,
            mean_anomaly=0.0,
            classification="",
            intl_designator="",
            element_set_no=0,
            rev_at_epoch=0,
            bstar="",
            mean_motion_dot="",
            mean_motion_ddot="",
        )
