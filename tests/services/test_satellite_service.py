from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from models.satellite import GroundStation, SatellitePass, SatellitePosition
from services.satellite_service import SatelliteService


class TestSatelliteService:
    """Test cases for SatellliteService."""

    def test_init(self, mock_spacetrack_service, mock_celestrak_service):
        """Test service initialization."""
        service = SatelliteService(mock_spacetrack_service, mock_celestrak_service)

        assert service.spacetrack == mock_spacetrack_service
        assert service.celestrak == mock_celestrak_service
        assert service.logger is not None

    @patch("services.satellite_service.load.timescale")
    @patch("services.satellite_service.EarthSatellite")
    @patch("services.satellite_service.Topos")
    def test_find_passes_success(
        self,
        mock_topos,
        mock_earth_satellite,
        mock_timescale,
        satellite_service,
        sample_tle_data,
    ):
        """Test successful satellite pass finding."""

        # Mock timescale
        mock_ts = Mock()
        mock_timescale.return_value = mock_ts

        # Mock time objects
        mock_t0 = Mock()
        mock_t1 = Mock()
        mock_ts.from_datetime.side_effect = [mock_t0, mock_t1]

        # Mock satellite and station
        mock_satellite = Mock()
        mock_earth_satellite.return_value = mock_satellite
        mock_station = Mock()
        mock_topos.return_value = mock_station

        # Mock pass events (rise=0, culminate=1, set=2)
        mock_time_rise = Mock()
        mock_time_rise.utc_strftime.return_value = "2024-06-15 10:00:00"
        mock_time_culminate = Mock()
        mock_time_culminate.utc_strftime.return_value = "2024-06-15 10:05:00"
        mock_time_set = Mock()
        mock_time_set.utc_strftime.return_value = "2024-06-15 10:10:00"

        mock_times = [mock_time_rise, mock_time_culminate, mock_time_set]
        mock_events = [0, 1, 2]  # rise, culminate, set
        mock_satellite.find_events.return_value = (mock_times, mock_events)

        mock_difference = Mock()
        mock_topocentric = Mock()
        mock_difference.at.return_value = mock_topocentric

        mock_satellite.__sub__ = Mock(return_value=mock_difference)

        mock_alt = Mock()
        mock_alt.degrees = 45.5
        mock_az = Mock()
        mock_distance = Mock()
        mock_topocentric.altaz.return_value = (mock_alt, mock_az, mock_distance)

        ground_station = GroundStation("Test Station", 52.0, 21.0, 100.0)
        start_time = datetime(2024, 6, 15, 0, 0, 0)
        end_time = datetime(2024, 6, 15, 23, 59, 59)

        result = satellite_service.find_passes(sample_tle_data, ground_station, start_time, end_time, 10.0)

        assert len(result) == 1
        assert isinstance(result[0], SatellitePass)
        assert result[0].rise_time_utc == "2024-06-15 10:00:00"
        assert result[0].culmination_time_utc == "2024-06-15 10:05:00"
        assert result[0].set_time_utc == "2024-06-15 10:10:00"
        assert result[0].max_elevation_degrees == 45.5

    @patch("services.satellite_service.load.timescale")
    @patch("services.satellite_service.EarthSatellite")
    def test_find_passes_no_passes(self, mock_earth_satellite, mock_timescale, satellite_service, sample_tle_data):
        """Test finding passes when no passes occur."""
        mock_ts = Mock()
        mock_timescale.return_value = mock_ts
        mock_satellite = Mock()
        mock_satellite = Mock()
        mock_earth_satellite.return_value = mock_satellite

        mock_satellite.find_events.return_value = ([], [])

        ground_station = GroundStation("Test Station", 52.0, 21.0, 100.0)
        start_time = datetime(2024, 6, 15, 0, 0, 0)
        end_time = datetime(2024, 6, 15, 23, 59, 59)

        result = satellite_service.find_passes(sample_tle_data, ground_station, start_time, end_time, 10.0)

        assert result == []

    def test_find_common_windows_overlap(self, satellite_service):
        """Test finding common windows with overlapping passes"""

        passes_gs1 = [
            SatellitePass(
                "2024-06-15 10:00:00",
                "2024-06-15 10:05:00",
                "2024-06-15 10:10:00",
                45.0,
            ),
            SatellitePass(
                "2024-06-15 14:00:00",
                "2024-06-15 14:05:00",
                "2024-06-15 14:10:00",
                30.0,
            ),
        ]

        passes_gs2 = [
            SatellitePass(
                "2024-06-15 10:02:00",
                "2024-06-15 10:07:00",
                "2024-06-15 10:12:00",
                40.0,
            ),
            SatellitePass(
                "2024-06-15 16:00:00",
                "2024-06-15 16:05:00",
                "2024-06-15 16:10:00",
                25.0,
            ),
        ]

        result = satellite_service.find_common_windows(passes_gs1, passes_gs2)
        assert len(result) == 1
        common = result[0]
        assert common["rise_time_utc"] == "2024-06-15 10:02:00"
        assert common["set_time_utc"] == "2024-06-15 10:10:00"
        assert common["max_elevation_degrees"] == 40.0  # minimum of the two
        assert common["duration_seconds"] == 480  # 8 minutes
        assert common["duration_str"] == "8m 0s"

    def test_find_common_windows_no_overlap(self, satellite_service):
        """Test finding common windows with no overlapping passes."""
        passes_gs1 = [
            SatellitePass(
                "2024-06-15 10:00:00",
                "2024-06-15 10:05:00",
                "2024-06-15 10:10:00",
                45.0,
            )
        ]

        passes_gs2 = [
            SatellitePass(
                "2024-06-15 14:00:00",
                "2024-06-15 14:05:00",
                "2024-06-15 14:10:00",
                40.0,
            )
        ]

        result = satellite_service.find_common_windows(passes_gs1, passes_gs2)

        assert result == []

    def test_find_common_windows_empty_lists(self, satellite_service):
        """Test finding common windows with empty pass lists."""
        result = satellite_service.find_common_windows([], [])
        assert result == []

        passes_gs1 = [
            SatellitePass(
                "2024-06-15 10:00:00",
                "2024-06-15 10:05:00",
                "2024-06-15 10:10:00",
                45.0,
            )
        ]

        result = satellite_service.find_common_windows(passes_gs1, [])
        assert result == []

    @patch("services.satellite_service.load.timescale")
    @patch("services.satellite_service.EarthSatellite")
    def test_calculate_position_success(
        self, mock_earth_satellite, mock_timescale, satellite_service, sample_tle_data
    ):
        """Test successful satellite position calculation."""
        # Mock timescale
        mock_ts = Mock()
        mock_timescale.return_value = mock_ts

        # Mock time object
        mock_t = Mock()
        mock_ts.from_datetime.return_value = mock_t

        # Mock satellite
        mock_satellite = Mock()
        mock_earth_satellite.return_value = mock_satellite

        # Mock geocentric position
        mock_geocentric = Mock()
        mock_satellite.at.return_value = mock_geocentric

        # Mock subpoint
        mock_subpoint = Mock()
        mock_subpoint.latitude.degrees = 52.123456
        mock_subpoint.longitude.degrees = 21.654321
        mock_subpoint.elevation.m = 408123.45
        mock_geocentric.subpoint.return_value = mock_subpoint

        calculation_time = datetime(2024, 6, 15, 12, 30, 45)
        result = satellite_service.calculate_position(sample_tle_data, calculation_time)

        assert isinstance(result, SatellitePosition)
        assert result.time_utc == "2024-06-15 12:30:45"
        assert result.latitude == 52.123456
        assert result.longitude == 21.654321
        assert result.elevation == 408123.45
        assert result.satellite_name == sample_tle_data.satellite_name

    @patch("services.satellite_service.load.timescale")
    @patch("services.satellite_service.EarthSatellite")
    def test_calculate_position_error_handling(
        self, mock_earth_satellite, mock_timescale, satellite_service, sample_tle_data
    ):
        """Test error handling in position calculation."""
        mock_earth_satellite.side_effect = Exception("Invalid TLE")

        calculation_time = datetime(2024, 6, 15, 12, 30, 45)

        with pytest.raises(Exception, match="Invalid TLE"):
            satellite_service.calculate_position(sample_tle_data, calculation_time)

    def test_parse_epoch_success(self, satellite_service):
        """Test successful epoch parsing with different formats."""
        test_cases = [
            ("2024-06-05T19:58:12.123456", datetime(2024, 6, 5, 19, 58, 12, 123456)),
            ("2024-06-05T19:58:12", datetime(2024, 6, 5, 19, 58, 12)),
            ("2024-06-05 19:58:12.123456", datetime(2024, 6, 5, 19, 58, 12, 123456)),
            ("2024-06-05 19:58:12", datetime(2024, 6, 5, 19, 58, 12)),
        ]

        for epoch_str, expected in test_cases:
            result = satellite_service._parse_epoch(epoch_str)
            assert result == expected

    def test_parse_epoch_invalid(self, satellite_service):
        """Test epoch parsing with invalid formats."""
        invalid_epochs = ["invalid-date", "", "2024-13-45T25:70:80"]

        for epoch_str in invalid_epochs:
            result = satellite_service._parse_epoch(epoch_str)
            assert result is None

    def test_parse_epoch_empty(self, satellite_service):
        """Test epoch parsing with empty string."""
        result = satellite_service._parse_epoch("")
        assert result is None

    def test_get_current_tle(self, satellite_service, sample_tle_data):
        """Test getting current TLE from CelesTrak."""
        satellite_service.celestrak.fetch_current_tle.return_value = sample_tle_data

        result = satellite_service.get_current_tle("25544")

        assert result == sample_tle_data
        satellite_service.celestrak.fetch_current_tle.assert_called_once_with("25544")

    def test_get_tle_history(self, satellite_service, sample_tle_data):
        """Test getting TLE history from SpaceTrack."""
        tle_list = [sample_tle_data]
        satellite_service.spacetrack.fetch_tle_history.return_value = tle_list

        result = satellite_service.get_tle_history("25544", 30)

        assert result == tle_list
        satellite_service.spacetrack.fetch_tle_history.assert_called_once_with("25544", 30)

    def test_get_tle_age_info(self, satellite_service):
        """Test getting TLE age information."""
        age_info = {
            "epoch": "2024-06-05T19:58:12.000000",
            "age_days": 1,
            "is_fresh": True,
            "warning": None,
        }
        satellite_service.spacetrack.get_latest_tle_age.return_value = age_info

        result = satellite_service.get_tle_age_info("25544")

        assert result == age_info
        satellite_service.spacetrack.get_latest_tle_age.assert_called_once_with("25544")


class TestSatelliteServiceIntegration:
    """Integration tests for SatelliteService."""

    @patch("services.satellite_service.load.timescale")
    @patch("services.satellite_service.EarthSatellite")
    @patch("services.satellite_service.Topos")
    def test_full_pass_calculation_workflow(
        self,
        mock_topos,
        mock_earth_satellite,
        mock_timescale,
        satellite_service,
        sample_tle_data,
    ):
        """Test complete pass calculation workflow."""
        # Setup mocks for two ground stations
        mock_ts = Mock()
        mock_timescale.return_value = mock_ts

        mock_satellite = Mock()
        mock_earth_satellite.return_value = mock_satellite

        # Create separate mock stations for each ground station
        mock_station1 = Mock()
        mock_station2 = Mock()

        # Track which station is being created
        station_call_count = 0

        def mock_topos_side_effect(**kwargs):
            nonlocal station_call_count
            station_call_count += 1
            if station_call_count == 1:
                return mock_station1
            else:
                return mock_station2

        mock_topos.side_effect = mock_topos_side_effect

        # Mock different passes for each station
        def mock_find_events(station, t0, t1, altitude_degrees):
            if station == mock_station1:  # First ground station (GS1)
                mock_times = [Mock(), Mock(), Mock()]
                mock_times[0].utc_strftime.return_value = "2024-06-15 10:00:00"
                mock_times[1].utc_strftime.return_value = "2024-06-15 10:05:00"
                mock_times[2].utc_strftime.return_value = "2024-06-15 10:10:00"
                return (mock_times, [0, 1, 2])
            else:  # Second ground station (GS2)
                mock_times = [Mock(), Mock(), Mock()]
                mock_times[0].utc_strftime.return_value = "2024-06-15 10:02:00"
                mock_times[1].utc_strftime.return_value = "2024-06-15 10:07:00"
                mock_times[2].utc_strftime.return_value = "2024-06-15 10:12:00"
                return (mock_times, [0, 1, 2])

        mock_satellite.find_events.side_effect = mock_find_events

        # Mock elevation calculation
        mock_difference = Mock()
        mock_satellite.__sub__ = Mock(return_value=mock_difference)
        mock_topocentric = Mock()
        mock_difference.at.return_value = mock_topocentric

        mock_alt = Mock()
        mock_alt.degrees = 45.0
        mock_topocentric.altaz.return_value = (mock_alt, Mock(), Mock())

        gs1 = GroundStation("Station 1", 52.0, 21.0, 100.0)
        gs2 = GroundStation("Station 2", 51.0, 20.0, 150.0)
        start_time = datetime(2024, 6, 15, 0, 0, 0)
        end_time = datetime(2024, 6, 15, 23, 59, 59)

        # Calculate passes for both stations
        passes_gs1 = satellite_service.find_passes(sample_tle_data, gs1, start_time, end_time, 10.0)
        passes_gs2 = satellite_service.find_passes(sample_tle_data, gs2, start_time, end_time, 10.0)

        # Find common windows
        common_windows = satellite_service.find_common_windows(passes_gs1, passes_gs2)

        assert len(passes_gs1) == 1
        assert len(passes_gs2) == 1
        assert len(common_windows) == 1
        assert common_windows[0]["rise_time_utc"] == "2024-06-15 10:02:00"
        assert common_windows[0]["set_time_utc"] == "2024-06-15 10:10:00"

    def test_service_delegation(self, satellite_service, sample_tle_data):
        """Test that service properly delegates to underlying services."""
        # Mock return values
        satellite_service.celestrak.fetch_current_tle.return_value = sample_tle_data
        satellite_service.spacetrack.fetch_tle_history.return_value = [sample_tle_data]
        satellite_service.spacetrack.get_latest_tle_age.return_value = {"age_days": 1}

        # Test delegation
        tle_result = satellite_service.get_current_tle("25544")
        history_result = satellite_service.get_tle_history("25544", 7)
        age_result = satellite_service.get_tle_age_info("25544")

        # Verify calls were made
        satellite_service.celestrak.fetch_current_tle.assert_called_once_with("25544")
        satellite_service.spacetrack.fetch_tle_history.assert_called_once_with("25544", 7)
        satellite_service.spacetrack.get_latest_tle_age.assert_called_once_with("25544")

        # Verify results
        assert tle_result == sample_tle_data
        assert history_result == [sample_tle_data]
        assert age_result == {"age_days": 1}


class TestSatelliteServiceEdgeCases:
    """Edge case tests for SatelliteService."""

    def test_find_passes_incomplete_events(self, satellite_service, sample_tle_data):
        """Test handling of incomplete event sequences."""
        with (
            patch("services.satellite_service.load.timescale") as mock_timescale,
            patch("services.satellite_service.EarthSatellite") as mock_earth_satellite,
            patch("services.satellite_service.Topos"),
        ):
            mock_ts = Mock()
            mock_timescale.return_value = mock_ts
            mock_satellite = Mock()
            mock_earth_satellite.return_value = mock_satellite

            # Incomplete event sequence (missing set event)
            mock_times = [Mock(), Mock()]
            mock_events = [0, 1]  # rise, culminate (no set)
            mock_satellite.find_events.return_value = (mock_times, mock_events)

            ground_station = GroundStation("Test Station", 52.0, 21.0, 100.0)
            start_time = datetime(2024, 6, 15, 0, 0, 0)
            end_time = datetime(2024, 6, 15, 23, 59, 59)

            result = satellite_service.find_passes(sample_tle_data, ground_station, start_time, end_time, 10.0)

            assert result == []  # No complete passes found

    def test_find_common_windows_complex_overlap(self, satellite_service):
        """Test complex overlapping scenarios."""
        passes_gs1 = [
            SatellitePass(
                "2024-06-15 10:00:00",
                "2024-06-15 10:05:00",
                "2024-06-15 10:10:00",
                45.0,
            ),
            SatellitePass(
                "2024-06-15 12:00:00",
                "2024-06-15 12:05:00",
                "2024-06-15 12:10:00",
                35.0,
            ),
        ]

        passes_gs2 = [
            SatellitePass(
                "2024-06-15 10:05:00",
                "2024-06-15 10:08:00",
                "2024-06-15 10:15:00",
                40.0,
            ),
            SatellitePass(
                "2024-06-15 11:58:00",
                "2024-06-15 12:03:00",
                "2024-06-15 12:08:00",
                30.0,
            ),
        ]

        result = satellite_service.find_common_windows(passes_gs1, passes_gs2)

        assert len(result) == 2

        # First common window
        assert result[0]["rise_time_utc"] == "2024-06-15 10:05:00"
        assert result[0]["set_time_utc"] == "2024-06-15 10:10:00"
        assert result[0]["max_elevation_degrees"] == 40.0

        # Second common window
        assert result[1]["rise_time_utc"] == "2024-06-15 12:00:00"
        assert result[1]["set_time_utc"] == "2024-06-15 12:08:00"
        assert result[1]["max_elevation_degrees"] == 30.0

    def test_calculate_position_precision(self, satellite_service, sample_tle_data):
        """Test position calculation precision."""
        with (
            patch("services.satellite_service.load.timescale") as mock_timescale,
            patch("services.satellite_service.EarthSatellite") as mock_earth_satellite,
        ):
            mock_ts = Mock()
            mock_timescale.return_value = mock_ts
            mock_satellite = Mock()
            mock_earth_satellite.return_value = mock_satellite

            mock_geocentric = Mock()
            mock_satellite.at.return_value = mock_geocentric

            # Test high precision coordinates
            mock_subpoint = Mock()
            mock_subpoint.latitude.degrees = 52.1234567890123
            mock_subpoint.longitude.degrees = 21.9876543210987
            mock_subpoint.elevation.m = 408123.456789
            mock_geocentric.subpoint.return_value = mock_subpoint

            calculation_time = datetime(2024, 6, 15, 12, 30, 45)
            result = satellite_service.calculate_position(sample_tle_data, calculation_time)

            # Check that precision is limited to 6 decimal places for lat/lon
            assert result.latitude == 52.123457  # Rounded to 6 decimals
            assert result.longitude == 21.987654  # Rounded to 6 decimals
            assert result.elevation == 408123.46  # Rounded to 2 decimals

    def test_find_passes_extreme_elevation(self, satellite_service, sample_tle_data):
        """Test passes with extreme elevation requirements."""
        with (
            patch("services.satellite_service.load.timescale") as mock_timescale,
            patch("services.satellite_service.EarthSatellite") as mock_earth_satellite,
            patch("services.satellite_service.Topos"),
        ):
            mock_ts = Mock()
            mock_timescale.return_value = mock_ts
            mock_satellite = Mock()
            mock_earth_satellite.return_value = mock_satellite

            # No events found due to high elevation requirement
            mock_satellite.find_events.return_value = ([], [])

            ground_station = GroundStation("Test Station", 52.0, 21.0, 100.0)
            start_time = datetime(2024, 6, 15, 0, 0, 0)
            end_time = datetime(2024, 6, 15, 23, 59, 59)
            min_elevation = 85.0  # Very high elevation requirement

            result = satellite_service.find_passes(
                sample_tle_data, ground_station, start_time, end_time, min_elevation
            )

            assert result == []
            mock_satellite.find_events.assert_called_once()
            # Verify high elevation was passed to find_events
            call_args = mock_satellite.find_events.call_args
            assert call_args[1]["altitude_degrees"] == 85.0
