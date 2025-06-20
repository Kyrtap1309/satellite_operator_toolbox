from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class TLEData:
    """Two-Line Element data model."""

    norad_id: str
    satellite_name: str
    tle_line1: str
    tle_line2: str
    epoch: str
    mean_motion: float
    eccentricity: float
    inclination: float
    ra_of_asc_node: float
    arg_of_pericenter: float
    mean_anomaly: float
    classification: Optional[str] = None
    intl_designator: Optional[str] = None
    element_set_no: Optional[int] = None
    rev_at_epoch: Optional[int] = None
    bstar: Optional[str] = None
    mean_motion_dot: Optional[str] = None
    mean_motion_ddot: Optional[str] = None
    period_minutes: Optional[float] = None

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
class GroundStation:
    """Ground station model."""

    name: str
    latitude: float
    longitude: float
    elevation: float


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
