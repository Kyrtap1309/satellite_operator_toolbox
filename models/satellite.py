from dataclasses import dataclass
from typing import Any


@dataclass
class GroundStation:
    """Ground station model."""

    name: str
    latitude: float
    longitude: float
    elevation: float


@dataclass
class TLEData:
    """Two-Line Element data model."""

    norad_id: str
    satellite_name: str
    tle_line1: str
    tle_line2: str
    epoch: str = ""
    mean_motion: float = 0.0
    eccentricity: float = 0.0
    inclination: float = 0.0
    ra_of_asc_node: float = 0.0
    arg_of_pericenter: float = 0.0
    mean_anomaly: float = 0.0
    classification: str | None = None
    intl_designator: str | None = None
    element_set_no: int | None = None
    rev_at_epoch: int | None = None
    bstar: str | None = None
    mean_motion_dot: str | None = None
    mean_motion_ddot: str | None = None
    period_minutes: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TLEData":
        """Create TLEData from dictionary."""
        return cls(
            norad_id=data.get("norad_id", ""),
            satellite_name=data.get("satellite_name", ""),
            tle_line1=data.get("tle_line1", ""),
            tle_line2=data.get("tle_line2", ""),
            epoch=data.get("epoch", ""),
            mean_motion=data.get("mean_motion", 0.0),
            eccentricity=data.get("eccentricity", 0.0),
            inclination=data.get("inclination", 0.0),
            ra_of_asc_node=data.get("ra_of_asc_node", 0.0),
            arg_of_pericenter=data.get("arg_of_pericenter", 0.0),
            mean_anomaly=data.get("mean_anomaly", 0.0),
            classification=data.get("classification"),
            intl_designator=data.get("intl_designator"),
            element_set_no=data.get("element_set_no"),
            rev_at_epoch=data.get("rev_at_epoch"),
            bstar=data.get("bstar"),
            mean_motion_dot=data.get("mean_motion_dot"),
            mean_motion_ddot=data.get("mean_motion_ddot"),
            period_minutes=data.get("period_minutes"),
        )


@dataclass
class SatellitePass:
    """Satellite pass data model."""

    rise_time_utc: str
    culmination_time_utc: str
    set_time_utc: str
    max_elevation_degrees: float


@dataclass
class SatellitePosition:
    """Satellite position data model."""

    time_utc: str
    latitude: float
    longitude: float
    elevation: float
    satellite_name: str
