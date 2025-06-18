import logging
from datetime import datetime
from typing import Any

from skyfield.api import EarthSatellite, Topos, load, utc  # type: ignore[import-untyped]

from models.satellite import (
    GroundStation,
    SatellitePass,
    SatellitePosition,
    TLEData,
)
from services.celestrak_service import CelestrakService
from services.database_service import DatabaseService
from services.spacetrack_service import SpaceTrackService

# Constants for satellite pass events
SATELLITE_EVENT_RISE = 0
SATELLITE_EVENT_CULMINATE = 1
SATELLITE_EVENT_SET = 2
PASS_EVENT_SEQUENCE_LENGTH = 3  # rise, culminate, set


class SatelliteService:
    """Main satellite operations service."""

    def __init__(
        self,
        spacetrack_service: SpaceTrackService,
        celestrak_service: CelestrakService,
        database_service: DatabaseService,
    ):
        self.spacetrack = spacetrack_service
        self.celestrak = celestrak_service
        self.database = database_service
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
            satellite = EarthSatellite(tle_data.tle_line1, tle_data.tle_line2, tle_data.satellite_name, ts)
            station = Topos(
                latitude_degrees=ground_station.latitude,
                longitude_degrees=ground_station.longitude,
                elevation_m=ground_station.elevation,
            )

            t0 = ts.from_datetime(start_time.replace(tzinfo=utc))
            t1 = ts.from_datetime(end_time.replace(tzinfo=utc))

            times, events = satellite.find_events(station, t0, t1, altitude_degrees=min_elevation)

            passes = []
            for i in range(0, len(events) - 2, PASS_EVENT_SEQUENCE_LENGTH):
                if events[i] == SATELLITE_EVENT_RISE and events[i + 1] == SATELLITE_EVENT_CULMINATE and events[i + 2] == SATELLITE_EVENT_SET:
                    rise_time = times[i]
                    culminate_time = times[i + 1]
                    set_time = times[i + 2]

                    # Calculate maximum elevation
                    difference = satellite - station
                    topocentric = difference.at(culminate_time)
                    alt, az, distance = topocentric.altaz()

                    pass_data = SatellitePass(
                        rise_time_utc=rise_time.utc_strftime("%Y-%m-%d %H:%M:%S"),
                        culmination_time_utc=culminate_time.utc_strftime("%Y-%m-%d %H:%M:%S"),
                        set_time_utc=set_time.utc_strftime("%Y-%m-%d %H:%M:%S"),
                        max_elevation_degrees=round(alt.degrees, 2),
                    )
                    passes.append(pass_data)

            return passes

        except Exception as e:
            self.logger.error(f"Error finding passes: {e}")
            raise

    def find_common_windows(self, passes_station1: list[SatellitePass], passes_station2: list[SatellitePass]) -> list[dict[str, Any]]:
        """Find common visibility windows between two stations."""
        common_windows = []

        for pass1 in passes_station1:
            for pass2 in passes_station2:
                # Parse times
                rise_time1 = datetime.strptime(pass1.rise_time_utc, "%Y-%m-%d %H:%M:%S")
                set_time1 = datetime.strptime(pass1.set_time_utc, "%Y-%m-%d %H:%M:%S")

                rise_time2 = datetime.strptime(pass2.rise_time_utc, "%Y-%m-%d %H:%M:%S")
                set_time2 = datetime.strptime(pass2.set_time_utc, "%Y-%m-%d %H:%M:%S")

                # Check for overlap
                if rise_time1 <= set_time2 and rise_time2 <= set_time1:
                    common_rise = max(rise_time1, rise_time2)
                    common_set = min(set_time1, set_time2)

                    min_elevation = min(pass1.max_elevation_degrees, pass2.max_elevation_degrees)
                    duration_sec = (common_set - common_rise).total_seconds()
                    duration_min = int(duration_sec // 60)
                    duration_sec_remainder = int(duration_sec % 60)

                    common_window = {
                        "rise_time_utc": common_rise.strftime("%Y-%m-%d %H:%M:%S"),
                        "set_time_utc": common_set.strftime("%Y-%m-%d %H:%M:%S"),
                        "max_elevation_degrees": min_elevation,
                        "duration_seconds": duration_sec,
                        "duration_str": f"{duration_min}m {duration_sec_remainder}s",
                    }
                    common_windows.append(common_window)

        return common_windows

    def calculate_position(self, tle_data: TLEData, time: datetime) -> SatellitePosition:
        """Calculate satellite position at given time."""
        try:
            ts = load.timescale()
            satellite = EarthSatellite(tle_data.tle_line1, tle_data.tle_line2, tle_data.satellite_name, ts)

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

    def _parse_epoch(self, epoch_str: str) -> datetime | None:
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
        """Get current TLE from database or fetch from CelesTrak."""
        # Ensure norad_id is a string
        norad_id_str = str(norad_id)

        # Try database first
        tle_data = self.database.get_latest_tle(norad_id_str)

        if tle_data:
            self.logger.info(f"Retrieved TLE for {norad_id_str} from database")
            return tle_data

        # Fallback to CelesTrak
        self.logger.info(f"Fetching TLE for {norad_id_str} from CelesTrak")
        tle_data = self.celestrak.fetch_current_tle(norad_id_str)

        # Save to database
        if tle_data:
            self.database.save_tle_data(tle_data, source="celestrak")

        return tle_data

    def get_tle_history(self, norad_id: str, days_back: int = 30) -> list[TLEData]:
        """Get TLE history - check database first, then fetch missing data from Space-Track."""
        norad_id_str = str(norad_id)

        # Sprawdź co mamy w bazie danych
        self.logger.info(f"Checking database for TLE history: {norad_id_str}")
        existing_history = self.database.get_tle_history(norad_id_str, days_back)

        # Jeśli mamy kompletną historię, zwróć ją
        if len(existing_history) >= days_back:
            self.logger.info(f"Found complete TLE history in database: {len(existing_history)} records for {norad_id_str}")
            return existing_history

        # Jeśli brakuje danych, sprawdź czy warto pobierać z Space-Track
        missing_days = days_back - len(existing_history) if existing_history else days_back

        self.logger.info(f"Database has {len(existing_history)} TLE records, missing ~{missing_days} days. Fetching from Space-Track...")

        try:
            # Pobierz z Space-Track z większym zakresem żeby złapać wszystkie brakujące dni
            fetch_days = max(days_back, 60)  # Pobierz więcej dni dla pewności
            spacetrack_history = self.spacetrack.fetch_tle_history(norad_id_str, fetch_days)

            # Zapisz nowe dane do bazy
            new_records_count = 0
            for tle_data in spacetrack_history:
                if self.database.save_tle_data(tle_data, source="spacetrack"):
                    new_records_count += 1

            self.logger.info(f"Fetched {len(spacetrack_history)} records from Space-Track, saved {new_records_count} new records")

            # Pobierz zaktualizowaną historię z bazy
            updated_history = self.database.get_tle_history(norad_id_str, days_back)
            self.logger.info(f"Final TLE history count: {len(updated_history)} records for {norad_id_str}")

            return updated_history

        except Exception as e:
            self.logger.warning(f"Failed to fetch from Space-Track: {e}")

            # Fallback - zwróć to co mamy w bazie, nawet jeśli niepełne
            if existing_history:
                self.logger.info(f"Using partial history from database: {len(existing_history)} records")
                return existing_history
            else:
                self.logger.warning(f"No TLE history found for {norad_id_str}")
                return []

    def get_tle_age_info(self, norad_id: str) -> dict[str, Any]:
        """Get TLE age information."""
        norad_id_str = str(norad_id)
        return self.spacetrack.get_latest_tle_age(norad_id_str)
