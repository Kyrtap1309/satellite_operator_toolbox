import logging
from datetime import datetime
from typing import Any, Optional

from skyfield.api import EarthSatellite, Topos, load, utc  # type: ignore

from models.satellite import (
    GroundStation,
    SatellitePass,
    SatellitePosition,
    TLEComparison,
    TLEData,
)
from services.celestrak_service import CelestrakService
from services.spacetrack_service import SpaceTrackService


class SatelliteService:
    """Main satellite operations service."""

    def __init__(
        self, spacetrack_service: SpaceTrackService, celestrak_service: CelestrakService
    ):
        self.spacetrack = spacetrack_service
        self.celestrak = celestrak_service
        self.logger = logging.getLogger(__name__)

    def find_passes(
        self,
        tle_data: TLEData,
        ground_station: GroundStation,
        start_time: datetime,
        end_time: datetime,
        min_elevation: float,
    ) -> list[SatellitePass]:
        """Find satellite passes for a ground station."""
        try:
            ts = load.timescale()
            satellite = EarthSatellite(
                tle_data.tle_line1, tle_data.tle_line2, tle_data.satellite_name, ts
            )
            station = Topos(
                latitude_degrees=ground_station.latitude,
                longitude_degrees=ground_station.longitude,
                elevation_m=ground_station.elevation,
            )

            t0 = ts.from_datetime(start_time.replace(tzinfo=utc))
            t1 = ts.from_datetime(end_time.replace(tzinfo=utc))

            times, events = satellite.find_events(
                station, t0, t1, altitude_degrees=min_elevation
            )

            passes = []
            for i in range(0, len(events) - 2, 3):
                if events[i] == 0 and events[i + 1] == 1 and events[i + 2] == 2:
                    rise_time = times[i]
                    culminate_time = times[i + 1]
                    set_time = times[i + 2]

                    # Calculate maximum elevation
                    difference = satellite - station
                    topocentric = difference.at(culminate_time)
                    alt, az, distance = topocentric.altaz()

                    pass_data = SatellitePass(
                        rise_time_utc=rise_time.utc_strftime("%Y-%m-%d %H:%M:%S"),
                        culmination_time_utc=culminate_time.utc_strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        set_time_utc=set_time.utc_strftime("%Y-%m-%d %H:%M:%S"),
                        max_elevation_degrees=round(alt.degrees, 2),
                    )
                    passes.append(pass_data)

            return passes

        except Exception as e:
            self.logger.error(f"Error finding passes: {e}")
            raise

    def find_common_windows(
        self, passes_station1: list[SatellitePass], passes_station2: list[SatellitePass]
    ) -> list[dict[str, Any]]:
        """Find common visibility windows between two stations."""
        common_windows = []

        for pass1 in passes_station1:
            rise_time1 = datetime.strptime(pass1.rise_time_utc, "%Y-%m-%d %H:%M:%S")
            set_time1 = datetime.strptime(pass1.set_time_utc, "%Y-%m-%d %H:%M:%S")

            for pass2 in passes_station2:
                rise_time2 = datetime.strptime(pass2.rise_time_utc, "%Y-%m-%d %H:%M:%S")
                set_time2 = datetime.strptime(pass2.set_time_utc, "%Y-%m-%d %H:%M:%S")

                # Check for overlap
                if rise_time1 <= set_time2 and rise_time2 <= set_time1:
                    common_rise = max(rise_time1, rise_time2)
                    common_set = min(set_time1, set_time2)

                    min_elevation = min(
                        pass1.max_elevation_degrees, pass2.max_elevation_degrees
                    )
                    duration_sec = (common_set - common_rise).total_seconds()
                    duration_min = int(duration_sec // 60)
                    duration_sec_remainder = int(duration_sec % 60)

                    common_window = {
                        "rise_time_utc": common_rise.strftime("%Y-%m-%d %H:%M:%S"),
                        "set_time_utc": common_set.strftime("%Y-%m-%d %H:%M:%S"),
                        "max_elevation_degrees": min_elevation,
                        "duration_seconds": duration_sec,
                        "duration_str": f"{duration_min}m {duration_sec_remainder}s",
                        "station1_rise": pass1.rise_time_utc,
                        "station1_set": pass1.set_time_utc,
                        "station1_max_el": pass1.max_elevation_degrees,
                        "station2_rise": pass2.rise_time_utc,
                        "station2_set": pass2.set_time_utc,
                        "station2_max_el": pass2.max_elevation_degrees,
                    }
                    common_windows.append(common_window)

        return sorted(common_windows, key=lambda x: x["rise_time_utc"])

    def calculate_position(
        self, tle_data: TLEData, time: datetime
    ) -> SatellitePosition:
        """Calculate satellite position at given time."""
        try:
            ts = load.timescale()
            satellite = EarthSatellite(
                tle_data.tle_line1, tle_data.tle_line2, tle_data.satellite_name, ts
            )

            t = ts.from_datetime(time.replace(tzinfo=utc))
            geocentric = satellite.at(t)
            subpoint = geocentric.subpoint()

            return SatellitePosition(
                time_utc=time.strftime("%Y-%m-%d %H:%M:%S"),
                latitude=round(subpoint.latitude.degrees, 6),
                longitude=round(subpoint.longitude.degrees, 6),
                elevation=round(subpoint.elevation.m, 2),
                satellite_name=tle_data.satellite_name,
            )

        except Exception as e:
            self.logger.error(f"Error calculating position: {e}")
            raise

    def compare_tle_elements(self, tle1: TLEData, tle2: TLEData) -> TLEComparison:
        """Compare two TLE datasets."""
        try:
            changes = []

            # Parse epochs
            epoch1 = self._parse_epoch(tle1.epoch)
            epoch2 = self._parse_epoch(tle2.epoch)
            epoch_diff_days = abs((epoch1 - epoch2).days) if epoch1 and epoch2 else 0

            # Calculate differences
            mean_motion_diff = abs(tle1.mean_motion - tle2.mean_motion)
            inclination_diff = abs(tle1.inclination - tle2.inclination)
            eccentricity_diff = abs(tle1.eccentricity - tle2.eccentricity)

            # Check for significant changes
            if mean_motion_diff > 0.001:
                changes.append("Significant mean motion change detected")
            if inclination_diff > 0.01:
                changes.append("Inclination change detected")
            if eccentricity_diff > 0.0001:
                changes.append("Eccentricity change detected")
            if epoch_diff_days > 7:
                changes.append("Large time gap between TLE epochs")

            # Check RAAN and argument of perigee
            raan_diff = abs(tle1.ra_of_asc_node - tle2.ra_of_asc_node)
            if raan_diff > 1.0:
                changes.append("RAAN change detected")

            arg_diff = abs(tle1.arg_of_pericenter - tle2.arg_of_pericenter)
            if arg_diff > 1.0:
                changes.append("Argument of perigee change detected")

            return TLEComparison(
                epoch_diff_days=epoch_diff_days,
                mean_motion_diff=mean_motion_diff,
                inclination_diff=inclination_diff,
                eccentricity_diff=eccentricity_diff,
                changes=changes,
            )

        except Exception as e:
            self.logger.error(f"Error comparing TLEs: {e}")
            return TLEComparison(
                epoch_diff_days=0,
                mean_motion_diff=0,
                inclination_diff=0,
                eccentricity_diff=0,
                changes=[],
                error=f"Error comparing TLE data: {e}",
            )

    def _parse_epoch(self, epoch_str: str) -> Optional[datetime]:
        """Parse epoch with multiple format support."""
        if not epoch_str:
            return None

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

        return None

    def get_current_tle(self, norad_id: str) -> TLEData:
        """Get current TLE from CelesTrak."""
        return self.celestrak.fetch_current_tle(norad_id)

    def get_tle_history(self, norad_id: str, days_back: int = 30) -> list[TLEData]:
        """Get TLE history from Space-Track."""
        return self.spacetrack.fetch_tle_history(norad_id, days_back)

    def get_tle_age_info(self, norad_id: str) -> dict[str, Any]:
        """Get TLE age information."""
        return self.spacetrack.get_latest_tle_age(norad_id)
