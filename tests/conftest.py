import tempfile

import pytest

from config import Config
from models.satellite import TLEData
from services.celestrak_service import CelestrakService


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    with tempfile.TemporaryDirectory():
        config = Config()
        config.CELESTRAK_BASE_URL = "https://celestrak.org/NORAD/elements/gp.php"
        config.LOG_LEVEL = "DEBUG"
        yield config


@pytest.fixture
def sample_tle_data():
    """Sample TLE data for testing."""
    return TLEData(
        norad_id="25544",
        satellite_name="ISS (ZARYA)",
        tle_line1="1 25544U 98067A   24157.83208333  .00002182  00000+0  40768-4 0  9990",
        tle_line2="2 25544  51.6461 339.7939 0001220  92.8340 267.3124 15.49309239456831",
        epoch="2024-06-05T19:58:12.000Z",
        mean_motion=15.49309239,
        eccentricity=0.0001220,
        inclination=51.6461,
        ra_of_asc_node=339.7939,
        arg_of_pericenter=92.8340,
        mean_anomaly=267.3124,
        classification="U",
        intl_designator="98067A",
        element_set_no=999,
        rev_at_epoch=45683,
        bstar="40768-4",
        mean_motion_dot="0.00002182",
        mean_motion_ddot="0",
        period_minutes=92.68,
    )


@pytest.fixture
def sample_json_response():
    """Sample JSON response from Celestrak API."""
    return [
        {
            "NORAD_CAT_ID": "25544",
            "EPOCH": "2024-06-05T19:58:12.000Z",
            "MEAN_MOTION": "15.49309239",
            "ECCENTRICITY": "0.0001220",
            "INCLINATION": "51.6461",
            "RA_OF_ASC_NODE": "339.7939",
            "ARG_OF_PERICENTER": "92.8340",
            "MEAN_ANOMALY": "267.3124",
            "CLASSIFICATION_TYPE": "U",
            "INTLDES": "98067A",
            "ELEMENT_SET_NO": "999",
            "REV_AT_EPOCH": "45683",
            "BSTAR": "40768-4",
            "MEAN_MOTION_DOT": "0.00002182",
            "MEAN_MOTION_DDOT": "0",
        }
    ]


@pytest.fixture
def sample_tle_response():
    """Sample TLE response from CelesTrak API."""
    return """ISS (ZARYA)
1 25544U 98067A   24157.83208333  .00002182  00000+0  40768-4 0  9990
2 25544  51.6461 339.7939 0001220  92.8340 267.3124 15.49309239456831"""


@pytest.fixture
def celestrak_service(mock_config):
    """CelestrakService instance for testing."""
    return CelestrakService(mock_config)
