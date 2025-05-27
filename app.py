import json
import logging
import os
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from typing import Any

import requests
from flask import Flask, redirect, render_template, request, url_for
from skyfield.api import EarthSatellite, Topos, load, utc

app = Flask(__name__)


# Configure logging
def setup_logging(app):
    """Configure logging for the application."""
    if not app.debug:
        # Production logging
        if not os.path.exists("logs"):
            os.mkdir("logs")

        file_handler = RotatingFileHandler(
            "logs/satellite_app.log",
            maxBytes=10240000,  # 10MB
            backupCount=10,
        )
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
            )
        )
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info("Satellite Operator Application startup")
    else:
        # Development logging
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        console_handler.setLevel(logging.DEBUG)

        app.logger.addHandler(console_handler)
        app.logger.setLevel(logging.DEBUG)
        app.logger.info("Satellite Operator Application startup (DEBUG mode)")


# Initialize logging
setup_logging(app)


class Config:
    SATELLITE_NAME = "Bluebon"
    SATELLITE_TLE_LINE1 = (
        "1 62688U 25009CH  25124.74930353  .00015765  00000+0  69252-3 0  9994"
    )
    SATELLITE_TLE_LINE2 = (
        "2 62688  97.4284 205.7904 0001127  28.6595 331.4703 15.22003295 16668"
    )

    STATION1_NAME = "Sweden"
    STATION1_LAT = 65.337
    STATION1_LON = 21.425
    STATION1_ELEV = 21

    STATION2_NAME = "Poland"
    STATION2_LAT = 51.097
    STATION2_LON = 17.069
    STATION2_ELEV = 116

    MIN_ELEVATION = 3.0


class SpaceTrackAPI:
    """Space-Track.org API client for fetching historical TLE data."""

    def __init__(self):
        self.base_url = "https://www.space-track.org"
        self.session = None
        self.username = os.getenv("SPACETRACK_USERNAME")
        self.password = os.getenv("SPACETRACK_PASSWORD")
        self.logger = logging.getLogger(__name__)

    def authenticate(self) -> bool:
        """Authenticate with SpaceTrack and maintain session."""
        if not self.username or not self.password:
            self.logger.error(
                "SpaceTrack credentials not found in environment variables"
            )
            return False

        self.logger.info(
            f"Attempting to authenticate with SpaceTrack as user: {self.username}"
        )

        try:
            self.session = requests.Session()

            login_url = f"{self.base_url}/ajaxauth/login"

            login_data = {"identity": self.username, "password": self.password}

            self.logger.debug(f"Sending login request to: {login_url}")
            response = self.session.post(login_url, data=login_data, timeout=30)
            response.raise_for_status()

            self.logger.debug(f"Login response status: {response.status_code}")

            # Test authentication with a simple query
            test_url = f"{self.base_url}/basicspacedata/query/class/tle_latest/NORAD_CAT_ID/25544/limit/1/format/json"
            self.logger.debug(f"Testing authentication with: {test_url}")
            test_response = self.session.get(test_url, timeout=30)

            if test_response.status_code == 200 and test_response.text.strip() != "[]":
                self.logger.info("SpaceTrack authentication successful")
                return True
            else:
                self.logger.error(
                    f"Authentication test failed. Status: {test_response.status_code}, Response: {test_response.text[:100]}"
                )
                return False

        except Exception as e:
            self.logger.error(f"Authentication failed: {e!s}")
            return False

    def fetch_tle_history(
        self, norad_id: str, days_back: int = 30
    ) -> list[dict[str, Any]]:
        """Fetch historical TLE data for a given NORAD ID."""
        self.logger.info(
            f"Fetching TLE history for NORAD ID {norad_id}, {days_back} days back"
        )

        if not self.authenticate():
            self.logger.error("Failed to authenticate for TLE history fetch")
            return [
                {
                    "error": "Authentication failed",
                    "message": "Could not authenticate with Space-Track.org. Check your credentials.",
                    "suggestion": "Verify SPACETRACK_USERNAME and SPACETRACK_PASSWORD environment variables.",
                }
            ]

        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            # Format dates for Space-Track API (YYYY-MM-DD)
            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")

            self.logger.debug(f"Date range: {start_date_str} to {end_date_str}")

            # Build query URL for historical TLE data
            query_url = (
                f"{self.base_url}/basicspacedata/query/class/tle/"
                f"NORAD_CAT_ID/{norad_id}/"
                f"EPOCH/{start_date_str}--{end_date_str}/"
                f"orderby/TLE_LINE1%20desc/"
                f"format/json"
            )

            self.logger.debug(f"Fetching TLE history from: {query_url}")
            response = self.session.get(query_url, timeout=30)
            response.raise_for_status()

            data = response.json()
            self.logger.info(
                f"Retrieved {len(data)} TLE entries for NORAD ID {norad_id}"
            )

            if not data:
                self.logger.warning(
                    f"No historical TLE data found for NORAD ID {norad_id}"
                )
                return [
                    {
                        "error": "No historical data found",
                        "message": f"No TLE history found for NORAD ID {norad_id} in the last {days_back} days.",
                        "suggestion": "Try increasing the date range or check if the NORAD ID is correct.",
                    }
                ]

            # Parse and format the historical TLE data
            historical_tles = []
            for tle_entry in data:
                try:
                    # Helper function to safely convert to float
                    def safe_float(value, default=0.0):
                        try:
                            return float(value) if value is not None else default
                        except (ValueError, TypeError):
                            return default

                    # Helper function to safely convert to int
                    def safe_int(value, default=0):
                        try:
                            return int(value) if value is not None else default
                        except (ValueError, TypeError):
                            return default

                    mean_motion = safe_float(tle_entry.get("MEAN_MOTION"))
                    period_minutes = (
                        round(1440 / mean_motion, 2) if mean_motion > 0 else None
                    )

                    historical_tles.append(
                        {
                            "norad_id": tle_entry.get("NORAD_CAT_ID"),
                            "satellite_name": tle_entry.get("OBJECT_NAME"),
                            "tle_line1": tle_entry.get("TLE_LINE1"),
                            "tle_line2": tle_entry.get("TLE_LINE2"),
                            "epoch": tle_entry.get("EPOCH"),
                            "mean_motion": mean_motion,
                            "eccentricity": safe_float(tle_entry.get("ECCENTRICITY")),
                            "inclination": safe_float(tle_entry.get("INCLINATION")),
                            "ra_of_asc_node": safe_float(
                                tle_entry.get("RA_OF_ASC_NODE")
                            ),
                            "arg_of_pericenter": safe_float(
                                tle_entry.get("ARG_OF_PERICENTER")
                            ),
                            "mean_anomaly": safe_float(tle_entry.get("MEAN_ANOMALY")),
                            "classification": tle_entry.get("CLASSIFICATION_TYPE"),
                            "intl_designator": tle_entry.get("INTLDES"),
                            "element_set_no": safe_int(tle_entry.get("ELEMENT_SET_NO")),
                            "rev_at_epoch": safe_int(tle_entry.get("REV_AT_EPOCH")),
                            "bstar": tle_entry.get("BSTAR"),
                            "mean_motion_dot": tle_entry.get("MEAN_MOTION_DOT"),
                            "mean_motion_ddot": tle_entry.get("MEAN_MOTION_DDOT"),
                            "period_minutes": period_minutes,
                        }
                    )
                except Exception as e:
                    self.logger.error(f"Error parsing TLE entry: {e}")
                    continue

            self.logger.info(f"Successfully parsed {len(historical_tles)} TLE entries")
            return historical_tles

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error while fetching TLE history: {e!s}")
            return [
                {
                    "error": "Network error",
                    "message": f"Failed to fetch data from Space-Track.org: {e!s}",
                    "suggestion": "Check your internet connection and try again.",
                }
            ]
        except Exception as e:
            self.logger.error(f"Unexpected error while fetching TLE history: {e!s}")
            return [
                {
                    "error": "Parsing error",
                    "message": f"Error processing Space-Track.org data: {e!s}",
                    "suggestion": "The data format may have changed. Contact support.",
                }
            ]

    def get_latest_tle_age(self, norad_id: str) -> dict[str, Any]:
        """Get the age of the latest TLE for a given satellite."""
        self.logger.info(f"Getting TLE age info for NORAD ID {norad_id}")

        if not self.authenticate():
            self.logger.error("Failed to authenticate for TLE age check")
            return {"error": "Authentication failed"}

        try:
            query_url = (
                f"{self.base_url}/basicspacedata/query/class/tle_latest/"
                f"NORAD_CAT_ID/{norad_id}/"
                f"format/json"
            )

            self.logger.debug(f"Fetching latest TLE from: {query_url}")
            response = self.session.get(query_url, timeout=30)
            response.raise_for_status()

            data = response.json()

            if not data:
                self.logger.warning(f"No TLE found for NORAD ID {norad_id}")
                return {"error": "No TLE found"}

            latest_tle = data[0]
            epoch_str = latest_tle.get("EPOCH")

            if epoch_str:
                # Try multiple date formats that Space-Track might return
                epoch_dt = None
                date_formats = [
                    "%Y-%m-%dT%H:%M:%S.%f",  # ISO format with microseconds
                    "%Y-%m-%dT%H:%M:%S",  # ISO format without microseconds
                    "%Y-%m-%d %H:%M:%S.%f",  # Space separated with microseconds
                    "%Y-%m-%d %H:%M:%S",  # Space separated without microseconds
                ]

                for date_format in date_formats:
                    try:
                        epoch_dt = datetime.strptime(epoch_str, date_format)
                        break
                    except ValueError:
                        continue

                if epoch_dt is None:
                    self.logger.error(f"Could not parse epoch date: {epoch_str}")
                    return {"error": f"Invalid epoch format: {epoch_str}"}

                age_days = (datetime.now() - epoch_dt).days

                self.logger.info(f"TLE for NORAD ID {norad_id} is {age_days} days old")

                return {
                    "epoch": epoch_str,
                    "age_days": age_days,
                    "is_fresh": age_days < 7,
                    "warning": "TLE is outdated" if age_days > 14 else None,
                }

            self.logger.error(f"Invalid epoch data for NORAD ID {norad_id}")
            return {"error": "Invalid epoch data"}

        except Exception as e:
            self.logger.error(f"Failed to check TLE age: {e!s}")
            return {"error": f"Failed to check TLE age: {e!s}"}

    def __del__(self):
        """Close the session when object is destroyed."""
        if self.session:
            self.session.close()
            self.logger.debug("SpaceTrack session closed")


class SatelliteTracker:
    @staticmethod
    def find_passes(
        tle_line1: str,
        tle_line2: str,
        tle_name: str,
        station_lat: float,
        station_lon: float,
        station_elev: float,
        start_time_str: str,
        end_time_str: str,
        min_el: float,
    ) -> list[dict[str, Any]]:
        ts = load.timescale()
        satellite = EarthSatellite(tle_line1, tle_line2, tle_name, ts)
        ground_station = Topos(
            latitude_degrees=station_lat,
            longitude_degrees=station_lon,
            elevation_m=station_elev,
        )

        start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=utc
        )
        end_dt = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=utc
        )

        t0 = ts.from_datetime(start_dt)
        t1 = ts.from_datetime(end_dt)

        times, events = satellite.find_events(
            ground_station, t0, t1, altitude_degrees=min_el
        )

        passes = []
        for i in range(0, len(events) - 2, 3):
            if events[i] == 0 and events[i + 1] == 1 and events[i + 2] == 2:
                rise_time = times[i]
                culminate_time = times[i + 1]
                set_time = times[i + 2]

                difference = satellite - ground_station
                topocentric = difference.at(culminate_time)
                alt, az, distance = topocentric.altaz()
                max_elevation = alt.degrees

                passes.append(
                    {
                        "rise_time_utc": rise_time.utc_strftime("%Y-%m-%d %H:%M:%S"),
                        "culmination_time_utc": culminate_time.utc_strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "set_time_utc": set_time.utc_strftime("%Y-%m-%d %H:%M:%S"),
                        "max_elevation_degrees": round(max_elevation, 2),
                    }
                )

        return passes

    @staticmethod
    def find_common_windows(
        passes_station1: list[dict[str, Any]], passes_station2: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        common_windows = []

        for pass1 in passes_station1:
            rise_time1 = datetime.strptime(pass1["rise_time_utc"], "%Y-%m-%d %H:%M:%S")
            set_time1 = datetime.strptime(pass1["set_time_utc"], "%Y-%m-%d %H:%M:%S")

            for pass2 in passes_station2:
                rise_time2 = datetime.strptime(
                    pass2["rise_time_utc"], "%Y-%m-%d %H:%M:%S"
                )
                set_time2 = datetime.strptime(
                    pass2["set_time_utc"], "%Y-%m-%d %H:%M:%S"
                )

                if rise_time1 <= set_time2 and rise_time2 <= set_time1:
                    common_rise = max(rise_time1, rise_time2)
                    common_set = min(set_time1, set_time2)

                    min_elevation = min(
                        pass1["max_elevation_degrees"], pass2["max_elevation_degrees"]
                    )

                    duration_sec = (common_set - common_rise).total_seconds()
                    duration_min = int(duration_sec // 60)
                    duration_sec_remainder = int(duration_sec % 60)
                    duration_str = f"{duration_min}m {duration_sec_remainder}s"

                    common_window = {
                        "rise_time_utc": common_rise.strftime("%Y-%m-%d %H:%M:%S"),
                        "set_time_utc": common_set.strftime("%Y-%m-%d %H:%M:%S"),
                        "max_elevation_degrees": min_elevation,
                        "duration_seconds": duration_sec,
                        "duration_str": duration_str,
                        "station1_rise": pass1["rise_time_utc"],
                        "station1_set": pass1["set_time_utc"],
                        "station1_max_el": pass1["max_elevation_degrees"],
                        "station2_rise": pass2["rise_time_utc"],
                        "station2_set": pass2["set_time_utc"],
                        "station2_max_el": pass2["max_elevation_degrees"],
                    }

                    common_windows.append(common_window)

        return sorted(common_windows, key=lambda x: x["rise_time_utc"])

    @staticmethod
    def calculate_position(
        tle_line1: str, tle_line2: str, tle_name: str, time_str: str
    ) -> dict[str, Any]:
        ts = load.timescale()
        satellite = EarthSatellite(tle_line1, tle_line2, tle_name, ts)

        time_dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=utc)
        t = ts.from_datetime(time_dt)

        geocentric = satellite.at(t)

        subpoint = geocentric.subpoint()

        return {
            "time_utc": time_str,
            "latitude": round(subpoint.latitude.degrees, 6),
            "longitude": round(subpoint.longitude.degrees, 6),
            "elevation": round(subpoint.elevation.m, 2),  # height in meters
            "satellite_name": tle_name,
        }

    @staticmethod
    def fetch_tle_from_celestrak(norad_id: str) -> dict[str, Any]:
        """Fetch current TLE data from CelesTrak for a given NORAD ID using both JSON and TLE endpoints."""
        try:
            # CelesTrak API endpoints
            json_url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad_id}&FORMAT=json"
            tle_url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad_id}&FORMAT=TLE"

            # Fetch JSON data for orbital parameters
            json_response = requests.get(json_url, timeout=10)
            json_response.raise_for_status()

            json_data = json_response.json()
            if not json_data:
                return {"error": f"No satellite data found for NORAD ID: {norad_id}"}

            # Extract satellite data from JSON
            sat_data = json_data[0]

            # Fetch TLE format data for the actual TLE lines
            tle_response = requests.get(tle_url, timeout=10)
            tle_response.raise_for_status()

            tle_data = tle_response.text.strip()
            if not tle_data:
                return {"error": f"No TLE data found for NORAD ID: {norad_id}"}

            # Parse TLE data (3 lines: name, line1, line2)
            lines = tle_data.split("\n")
            if len(lines) < 3:
                return {"error": "Invalid TLE format received"}

            satellite_name = lines[0].strip()
            tle_line1 = lines[1].strip()
            tle_line2 = lines[2].strip()

            # Combine data from both sources
            return {
                # Basic identification
                "norad_id": sat_data.get("NORAD_CAT_ID"),
                "satellite_name": satellite_name,  # From TLE format (more reliable)
                # TLE lines (from TLE endpoint)
                "tle_line1": tle_line1,
                "tle_line2": tle_line2,
                # Orbital parameters (from JSON endpoint - more precise)
                "epoch": sat_data.get("EPOCH"),
                "mean_motion": sat_data.get("MEAN_MOTION"),
                "eccentricity": sat_data.get("ECCENTRICITY"),
                "inclination": sat_data.get("INCLINATION"),
                "ra_of_asc_node": sat_data.get("RA_OF_ASC_NODE"),
                "arg_of_pericenter": sat_data.get("ARG_OF_PERICENTER"),
                "mean_anomaly": sat_data.get("MEAN_ANOMALY"),
                # Additional metadata (from JSON endpoint)
                "classification": sat_data.get("CLASSIFICATION_TYPE"),
                "intl_designator": sat_data.get("INTLDES"),
                "element_set_no": sat_data.get("ELEMENT_SET_NO"),
                "rev_at_epoch": sat_data.get("REV_AT_EPOCH"),
                "bstar": sat_data.get("BSTAR"),
                "mean_motion_dot": sat_data.get("MEAN_MOTION_DOT"),
                "mean_motion_ddot": sat_data.get("MEAN_MOTION_DDOT"),
                # Calculated fields
                "period_minutes": round(1440 / float(sat_data.get("MEAN_MOTION", 1)), 2)
                if sat_data.get("MEAN_MOTION")
                else None,
                "apogee_km": None,  # Would need additional calculation
                "perigee_km": None,  # Would need additional calculation
            }

        except requests.exceptions.RequestException as e:
            return {"error": f"Failed to fetch TLE data: {e!s}"}
        except (KeyError, IndexError, ValueError) as e:
            return {"error": f"Error parsing TLE data: {e!s}"}

    @staticmethod
    def fetch_tle_history_from_spacetrack(
        norad_id: str, days_back: int = 30
    ) -> list[dict[str, Any]]:
        spacetrack = SpaceTrackAPI()
        return spacetrack.fetch_tle_history(norad_id, days_back)

    @staticmethod
    def get_tle_age_info(norad_id: str) -> dict[str, Any]:
        """Get TLE age information from SpaceTrack"""
        spacetrack = SpaceTrackAPI()
        return spacetrack.get_latest_tle_age(norad_id)

    @staticmethod
    def compare_tle_elements(
        tle1: dict[str, Any], tle2: dict[str, Any]
    ) -> dict[str, Any]:
        """Compare two TLE datasets and highlight differences."""
        if "error" in tle1 or "error" in tle2:
            return {"error": "Cannot compare TLE data due to fetch errors"}

        comparison = {
            "epoch_diff_days": 0,
            "mean_motion_diff": 0,
            "inclination_diff": 0,
            "eccentricity_diff": 0,
            "changes": [],
        }

        try:
            # Helper function to parse different date formats
            def parse_epoch(epoch_str):
                if not epoch_str:
                    return None

                date_formats = [
                    "%Y-%m-%dT%H:%M:%S.%f",  # ISO format with microseconds
                    "%Y-%m-%dT%H:%M:%S",  # ISO format without microseconds
                    "%Y-%m-%d %H:%M:%S.%f",  # Space separated with microseconds
                    "%Y-%m-%d %H:%M:%S",  # Space separated without microseconds
                ]

                for date_format in date_formats:
                    try:
                        return datetime.strptime(epoch_str, date_format)
                    except ValueError:
                        continue

                # If all formats fail, raise an error
                raise ValueError(f"Could not parse epoch: {epoch_str}")

            # Compare epochs
            epoch1 = parse_epoch(tle1.get("epoch", ""))
            epoch2 = parse_epoch(tle2.get("epoch", ""))

            if epoch1 and epoch2:
                comparison["epoch_diff_days"] = abs((epoch1 - epoch2).days)

            # Helper function to safely get float values
            def safe_float(value):
                if value is None:
                    return 0.0
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return 0.0

            # Compare orbital elements
            mean_motion1 = safe_float(tle1.get("mean_motion"))
            mean_motion2 = safe_float(tle2.get("mean_motion"))
            if mean_motion1 and mean_motion2:
                comparison["mean_motion_diff"] = abs(mean_motion1 - mean_motion2)

            inclination1 = safe_float(tle1.get("inclination"))
            inclination2 = safe_float(tle2.get("inclination"))
            if inclination1 and inclination2:
                comparison["inclination_diff"] = abs(inclination1 - inclination2)

            eccentricity1 = safe_float(tle1.get("eccentricity"))
            eccentricity2 = safe_float(tle2.get("eccentricity"))
            if eccentricity1 and eccentricity2:
                comparison["eccentricity_diff"] = abs(eccentricity1 - eccentricity2)

            # Track significant changes
            if comparison["mean_motion_diff"] > 0.001:
                comparison["changes"].append("Significant mean motion change detected")
            if comparison["inclination_diff"] > 0.01:
                comparison["changes"].append("Inclination change detected")
            if comparison["eccentricity_diff"] > 0.0001:
                comparison["changes"].append("Eccentricity change detected")

            # Check for major epoch differences
            if comparison["epoch_diff_days"] > 7:
                comparison["changes"].append("Large time gap between TLE epochs")

            # Additional checks
            raan1 = safe_float(tle1.get("ra_of_asc_node"))
            raan2 = safe_float(tle2.get("ra_of_asc_node"))
            if raan1 and raan2:
                raan_diff = abs(raan1 - raan2)
                if raan_diff > 1.0:  # More than 1 degree change
                    comparison["changes"].append("RAAN change detected")

            arg_perigee1 = safe_float(tle1.get("arg_of_pericenter"))
            arg_perigee2 = safe_float(tle2.get("arg_of_pericenter"))
            if arg_perigee1 and arg_perigee2:
                arg_diff = abs(arg_perigee1 - arg_perigee2)
                if arg_diff > 1.0:  # More than 1 degree change
                    comparison["changes"].append("Argument of perigee change detected")

        except Exception as e:
            comparison["error"] = f"Error comparing TLE data: {e!s}"

        return comparison


class DataFormatter:
    @staticmethod
    def format_passes_for_display(passes: list[dict[str, Any]]) -> list[dict[str, any]]:
        formatted_passes = []
        for i, pass_info in enumerate(passes, 1):
            rise_time = pass_info["rise_time_utc"]
            set_time = pass_info["set_time_utc"]
            max_el = pass_info["max_elevation_degrees"]
            date = rise_time.split()[0]
            rise_time_hm = rise_time.split()[1][:-3]
            set_time_hm = set_time.split()[1][:-3]

            formatted_passes.append(
                {
                    "Nr": i,
                    "Date": date,
                    "Rise Time (UTC)": rise_time_hm,
                    "Set Time (UTC)": set_time_hm,
                    "Max Elevation": f"{max_el:.1f}°",
                }
            )
        return formatted_passes

    @staticmethod
    def format_common_windows(
        common_windows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        formatted_common = []
        for i, window in enumerate(common_windows, 1):
            rise_time = window["rise_time_utc"]
            set_time = window["set_time_utc"]
            max_el = window["max_elevation_degrees"]

            date = rise_time.split()[0]
            rise_time_hm = rise_time.split()[1][:-3]
            set_time_hm = set_time.split()[1][:-3]

            formatted_common.append(
                {
                    "Nr": i,
                    "Date": date,
                    "Start (UTC)": rise_time_hm,
                    "End (UTC)": set_time_hm,
                    "Max Elevation": f"{max_el:.1f}°",
                    "Duration": window["duration_str"],
                }
            )
        return formatted_common

    @staticmethod
    def prepare_timeline_data(
        passes_gs1: list[dict[str, Any]],
        passes_gs2: list[dict[str, Any]],
        common_windows: list[dict[str, Any]],
        gs1_name: str,
        gs2_name: str,
    ) -> list[dict[str, Any]]:
        timeline_data = []
        for pass_info in passes_gs1:
            timeline_data.append(
                {
                    "group": gs1_name,
                    "start": pass_info["rise_time_utc"],
                    "end": pass_info["set_time_utc"],
                    "content": f"Max El: {pass_info['max_elevation_degrees']:.1f}°",
                    "type": "range",
                    "className": "gs1-pass",
                }
            )

        for pass_info in passes_gs2:
            timeline_data.append(
                {
                    "group": gs2_name,
                    "start": pass_info["rise_time_utc"],
                    "end": pass_info["set_time_utc"],
                    "content": f"Max El: {pass_info['max_elevation_degrees']:.1f}°",
                    "type": "range",
                    "className": "gs2-pass",
                }
            )

        for window in common_windows:
            timeline_data.append(
                {
                    "group": "Common",
                    "start": window["rise_time_utc"],
                    "end": window["set_time_utc"],
                    "content": f"Max El: {window['max_elevation_degrees']:.1f}° | {window['duration_str']}",
                    "type": "range",
                    "className": "common-window",
                }
            )

        return timeline_data


@app.route("/")
def index():
    app.logger.debug("Index page accessed")
    tomorrow = datetime.now() + timedelta(days=1)
    default_date = tomorrow.strftime("%Y-%m-%d")

    return render_template(
        "index.html",
        gs1_name=Config.STATION1_NAME,
        gs1_lat=Config.STATION1_LAT,
        gs1_lon=Config.STATION1_LON,
        gs1_elev=Config.STATION1_ELEV,
        gs2_name=Config.STATION2_NAME,
        gs2_lat=Config.STATION2_LAT,
        gs2_lon=Config.STATION2_LON,
        gs2_elev=Config.STATION2_ELEV,
        min_el=Config.MIN_ELEVATION,
        default_date=default_date,
        tle_name=Config.SATELLITE_NAME,
        tle_line1=Config.SATELLITE_TLE_LINE1,
        tle_line2=Config.SATELLITE_TLE_LINE2,
    )


@app.route("/calculate", methods=["POST"])
def calculate():
    app.logger.info("Pass calculation requested")
    form_data = request.form

    tle_name = form_data.get("tle_name", Config.SATELLITE_NAME)
    tle_line1 = form_data.get("tle_line1", Config.SATELLITE_TLE_LINE1)
    tle_line2 = form_data.get("tle_line2", Config.SATELLITE_TLE_LINE2)

    gs1_name = form_data.get("gs1_name", Config.STATION1_NAME)
    gs2_name = form_data.get("gs2_name", Config.STATION2_NAME)

    gs1_lat = float(form_data.get("gs1_lat", Config.STATION1_LAT))
    gs1_lon = float(form_data.get("gs1_lon", Config.STATION1_LON))
    gs1_elev = float(form_data.get("gs1_elev", Config.STATION1_ELEV))

    gs2_lat = float(form_data.get("gs2_lat", Config.STATION2_LAT))
    gs2_lon = float(form_data.get("gs2_lon", Config.STATION2_LON))
    gs2_elev = float(form_data.get("gs2_elev", Config.STATION2_ELEV))

    min_el = float(form_data.get("min_el", Config.MIN_ELEVATION))

    date = form_data.get("date")
    start_time = f"{date} 00:00:00"
    end_time = f"{date} 23:59:59"

    app.logger.info(
        f"Calculating passes for {tle_name} on {date} between {gs1_name} and {gs2_name}"
    )

    tracker = SatelliteTracker()
    passes_gs1 = tracker.find_passes(
        tle_line1,
        tle_line2,
        tle_name,
        gs1_lat,
        gs1_lon,
        gs1_elev,
        start_time,
        end_time,
        min_el,
    )

    passes_gs2 = tracker.find_passes(
        tle_line1,
        tle_line2,
        tle_name,
        gs2_lat,
        gs2_lon,
        gs2_elev,
        start_time,
        end_time,
        min_el,
    )

    common_windows = tracker.find_common_windows(passes_gs1, passes_gs2)

    formatter = DataFormatter()
    formatted_gs1 = formatter.format_passes_for_display(passes_gs1)
    formatted_gs2 = formatter.format_passes_for_display(passes_gs2)
    formatted_common = formatter.format_common_windows(common_windows)

    timeline_data = formatter.prepare_timeline_data(
        passes_gs1, passes_gs2, common_windows, gs1_name, gs2_name
    )

    app.logger.info(
        f"Calculation completed. Found {len(formatted_common)} common windows"
    )

    return render_template(
        "results.html",
        gs1_name=gs1_name,
        gs2_name=gs2_name,
        gs1_passes=formatted_gs1,
        gs2_passes=formatted_gs2,
        common_windows=formatted_common,
        timeline_data=json.dumps(timeline_data),
        date=date,
        gs1_lat=gs1_lat,
        gs1_lon=gs1_lon,
        gs1_elev=gs1_elev,
        gs2_lat=gs2_lat,
        gs2_lon=gs2_lon,
        gs2_elev=gs2_elev,
    )


@app.route("/position")
def position():
    """Render the satellite position calculator page."""
    now = datetime.now()
    default_date = now.strftime("%Y-%m-%d")
    default_time = now.strftime("%H:%M:%S")

    default_time_hm = default_time.rsplit(":", 1)[0]

    return render_template(
        "position_calculator.html",
        tle_name=Config.SATELLITE_NAME,
        tle_line1=Config.SATELLITE_TLE_LINE1,
        tle_line2=Config.SATELLITE_TLE_LINE2,
        default_date=default_date,
        default_time=default_time_hm,
    )


@app.route("/calculate_position", methods=["POST"])
def calculate_position():
    """Calculate and display the satellite position."""

    form_data = request.form

    tle_name = form_data.get("tle_name", Config.SATELLITE_NAME)
    tle_line1 = form_data.get("tle_line1", Config.SATELLITE_TLE_LINE1)
    tle_line2 = form_data.get("tle_line2", Config.SATELLITE_TLE_LINE2)

    date = form_data.get("date")
    time = form_data.get("time")

    datetime_str = f"{date} {time}:00"

    tracker = SatelliteTracker()
    position_data = tracker.calculate_position(
        tle_line1, tle_line2, tle_name, datetime_str
    )

    return render_template(
        "position_calculator.html",
        tle_name=tle_name,
        tle_line1=tle_line1,
        tle_line2=tle_line2,
        default_date=date,
        default_time=time,
        position_data=position_data,
    )


@app.route("/tle-viewer")
def tle_viewer():
    """Render the TLE history viewer page."""
    return render_template(
        "tle_viewer.html",
        norad_id="25544",  # Default to ISS
        days_back=30,
    )


@app.route("/fetch_tle_data", methods=["POST"])
def fetch_tle_data():
    """Fetch and display TLE data for a given NORAD ID."""
    form_data = request.form

    norad_id = form_data.get("norad_id", "25544")
    days_back = int(form_data.get("days_back", 30))

    app.logger.info(
        f"TLE data fetch requested for NORAD ID {norad_id}, {days_back} days back"
    )

    tracker = SatelliteTracker()

    # Fetch current TLE
    app.logger.debug("Fetching current TLE from CelesTrak")
    current_tle = tracker.fetch_tle_from_celestrak(norad_id)

    # Fetch TLE history
    app.logger.debug("Fetching TLE history from Space-Track")
    tle_history = tracker.fetch_tle_history_from_spacetrack(norad_id, days_back)

    # Get TLE age info
    app.logger.debug("Getting TLE age information")
    tle_age_info = tracker.get_tle_age_info(norad_id)

    # Compare TLEs if available
    comparison = None
    if (
        not current_tle.get("error")
        and tle_history
        and len(tle_history) > 0
        and not tle_history[0].get("error")
    ):
        app.logger.debug("Comparing current TLE with historical data")
        comparison = tracker.compare_tle_elements(current_tle, tle_history[0])

    app.logger.info("TLE data fetch completed successfully")

    return render_template(
        "tle_viewer.html",
        norad_id=norad_id,
        days_back=days_back,
        current_tle=current_tle,
        tle_history=tle_history,
        tle_age_info=tle_age_info,
        comparison=comparison,
    )


@app.route("/import_tle/<norad_id>")
def import_tle(norad_id):
    """Import TLE data and redirect to the pass calculator with the data populated."""
    tracker = SatelliteTracker()
    tle_data = tracker.fetch_tle_from_celestrak(norad_id)

    if tle_data.get("error"):
        return redirect(
            url_for(
                "index",
                error=f"Failed to import TLE for NORAD ID {norad_id}: {tle_data['error']}",
            )
        )

    tomorrow = datetime.now() + timedelta(days=1)
    default_date = tomorrow.strftime("%Y-%m-%d")

    return render_template(
        "index.html",
        success=f"TLE data imported for {tle_data['satellite_name']}",
        gs1_name=Config.STATION1_NAME,
        gs1_lat=Config.STATION1_LAT,
        gs1_lon=Config.STATION1_LON,
        gs1_elev=Config.STATION1_ELEV,
        gs2_name=Config.STATION2_NAME,
        gs2_lat=Config.STATION2_LAT,
        gs2_lon=Config.STATION2_LON,
        gs2_elev=Config.STATION2_ELEV,
        min_el=Config.MIN_ELEVATION,
        default_date=default_date,
        tle_name=tle_data["satellite_name"],
        tle_line1=tle_data["tle_line1"],
        tle_line2=tle_data["tle_line2"],
    )


# Error handlers with logging
@app.errorhandler(404)
def not_found_error(error):
    app.logger.warning(f"404 error: {request.url}")
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"500 error: {error!s}")
    return render_template("500.html"), 500


if __name__ == "__main__":
    app.logger.info("Starting Satellite Operator Application")
    app.run(host="0.0.0.0", port=5000, debug=True)
