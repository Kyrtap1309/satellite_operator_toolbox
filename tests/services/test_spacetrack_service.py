from datetime import datetime
from typing import Any
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import HTTPError, Timeout

from config import Config
from models.satellite import TLEData
from services.spacetrack_service import SpaceTrackService


class TestSpaceTrackService:
    """Test cases for SpaceTrackService."""

    def test_init(self, mock_config: Config):
        """Test service initialization."""
        service = SpaceTrackService(mock_config)

        assert service.config == mock_config
        assert service.base_url == mock_config.SPACETRACK_BASE_URL
        assert service.session is None
        assert service.logger is not None

    def test_init_no_credentials(self):
        """Test initialization without credentials."""
        config = Config()
        config.SPACETRACK_USERNAME = ""
        config.SPACETRACK_PASSWORD = ""

        service = SpaceTrackService(config)
        assert service.config == config

    @patch("services.spacetrack_service.requests.Session")
    def test_authenticate_success(self, mock_session_class, spacetrack_service: SpaceTrackService):
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_login_response = Mock()
        mock_login_response.raise_for_status.return_value = None
        mock_session.post.return_value = mock_login_response

        mock_test_response = Mock()
        mock_test_response.status_code = 200
        mock_test_response.text = '[{"test": "data"}]'
        mock_session.get.return_value = mock_test_response

        result = spacetrack_service.authenticate()

        assert result
        assert spacetrack_service.session == mock_session
        mock_session.post.assert_called_once()
        mock_session.get.assert_called_once()

    @patch("services.spacetrack_service.requests.Session")
    def test_authenticate_failure_no_credentials(self, mock_session_class):
        """Test authentication failure with no credentials."""
        config = Config()
        config.SPACETRACK_USERNAME = ""
        config.SPACETRACK_PASSWORD = ""

        service = SpaceTrackService(config)
        result = service.authenticate()

        assert not result
        assert service.session is None

    @patch("services.spacetrack_service.requests.Session")
    def test_authenticate_login_failure(self, mock_session_class, spacetrack_service: SpaceTrackService):
        """Test authentication failure durign login."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_session.post.side_effect = HTTPError("Login failed")

        result = spacetrack_service.authenticate()

        assert not result
        assert spacetrack_service.session is None

    @patch("services.spacetrack_service.requests.Session")
    def test_authenticate_test_failure(self, mock_session_class, spacetrack_service: SpaceTrackService):
        """Test authentication failure during test request."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_login_response = Mock()
        mock_login_response.raise_for_status.return_value = None
        mock_session.post.return_value = mock_login_response

        mock_test_response = Mock()
        mock_test_response.status_code = 401
        mock_test_response.text = "[]"
        mock_session.get.return_value = mock_test_response

        result = spacetrack_service.authenticate()

        assert not result

    def test_ensure_authenticated_success(self, spacetrack_service: SpaceTrackService):
        """Test _ensure_authenticated when already authenticated."""
        mock_session = Mock()
        spacetrack_service.session = mock_session

        result = spacetrack_service._ensure_authenticated()

        assert result == mock_session

    @patch.object(SpaceTrackService, "authenticate")
    def test_ensure_authenticated_authentication_needed(
        self, mock_authenticate, spacetrack_service: SpaceTrackService
    ):
        """Test _ensure_authenticated when authentication is needed."""
        spacetrack_service.session = None

        mock_session = Mock()

        def authenticate_side_effect():
            spacetrack_service.session = mock_session
            return True

        mock_authenticate.side_effect = authenticate_side_effect

        result = spacetrack_service._ensure_authenticated()

        assert result == mock_session
        mock_authenticate.assert_called_once()

    @patch.object(SpaceTrackService, "authenticate")
    def test_ensure_authenticated_authentication_failure(
        self, mock_authenticate, spacetrack_service: SpaceTrackService
    ):
        """Test _ensure_authenticated when authentication fails."""
        spacetrack_service.session = None
        mock_authenticate.return_value = False

        with pytest.raises(Exception, match="Authentication failed"):
            spacetrack_service._ensure_authenticated()

    @patch.object(SpaceTrackService, "_ensure_authenticated")
    def test_fetch_tle_history_success(
        self,
        mock_ensure_auth,
        spacetrack_service: SpaceTrackService,
        sample_spacetrack_history_response,
    ):
        """Test successful TLE history fetch."""

        mock_session = Mock()
        mock_ensure_auth.return_value = mock_session

        mock_response = Mock()
        mock_response.json.return_value = sample_spacetrack_history_response
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        result = spacetrack_service.fetch_tle_history("25544", 30)

        assert len(result) == 2
        assert all(isinstance(tle, TLEData) for tle in result)
        assert result[0].norad_id == "25544"
        assert result[0].satellite_name == "ISS (ZARYA)"
        assert len(result[0].tle_line1) == 69
        assert len(result[0].tle_line2) == 69

        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args[0][0]
        assert "25544" in call_args
        assert "class/tle/" in call_args
        assert "format/json" in call_args

    @patch.object(SpaceTrackService, "_ensure_authenticated")
    def test_fetch_tle_history_empty_response(self, mock_ensure_auth, spacetrack_service: SpaceTrackService):
        """Test TLE history fetch with empty response."""
        mock_session = Mock()
        mock_ensure_auth.return_value = mock_session

        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        result = spacetrack_service.fetch_tle_history("999999", 30)

        assert result == []

    @patch.object(SpaceTrackService, "_ensure_authenticated")
    def test_fetch_tle_history_http_error(self, mock_ensure_auth, spacetrack_service: SpaceTrackService):
        """Test TLE history fetch with HTTP error."""
        mock_session = Mock()
        mock_ensure_auth.return_value = mock_session

        mock_session.get.side_effect = HTTPError("404 Not Found")

        with pytest.raises(HTTPError):
            spacetrack_service.fetch_tle_history("25544", 30)

    @patch.object(SpaceTrackService, "_ensure_authenticated")
    def test_fetch_tle_history_timeout(self, mock_ensure_auth, spacetrack_service: SpaceTrackService):
        """Test TLE history fetch with timeout."""
        mock_session = Mock()
        mock_ensure_auth.return_value = mock_session

        mock_session.get.side_effect = Timeout("404 Not Found")

        with pytest.raises(Timeout):
            spacetrack_service.fetch_tle_history("25544", 30)

    @patch.object(SpaceTrackService, "_ensure_authenticated")
    def test_get_latest_tle_age_success(
        self,
        mock_ensure_auth,
        spacetrack_service: SpaceTrackService,
        sample_spacetrack_age_response,
    ):
        """Test successful TLE age fetch."""

        mock_session = Mock()
        mock_ensure_auth.return_value = mock_session

        mock_response = Mock()
        mock_response.json.return_value = sample_spacetrack_age_response
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        with patch("services.spacetrack_service.datetime") as mock_datetime:
            mock_now = datetime(2024, 6, 6, 19, 58, 12)
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime = datetime.strptime

            result = spacetrack_service.get_latest_tle_age("25544")

        assert "epoch" in result
        assert "age_days" in result
        assert "is_fresh" in result
        assert result["epoch"] == "2024-06-05T19:58:12.000000"
        assert result["age_days"] == 1

    @patch.object(SpaceTrackService, "_ensure_authenticated")
    def test_get_latest_tle_age_no_data(self, mock_ensure_auth, spacetrack_service: SpaceTrackService):
        """Test TLE age fetch with no data."""
        mock_session = Mock()
        mock_ensure_auth.return_value = mock_session

        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        with pytest.raises(Exception, match="No TLE found"):
            spacetrack_service.get_latest_tle_age("999999")

    def test_parse_tle_history_success(
        self, spacetrack_service: SpaceTrackService, sample_spacetrack_history_response
    ):
        """Test successful TLE history parsing."""
        result = spacetrack_service._parse_tle_history(sample_spacetrack_history_response)

        assert len(result) == 2
        tle = result[0]
        assert isinstance(tle, TLEData)
        assert tle.norad_id == "25544"
        assert tle.satellite_name == "ISS (ZARYA)"
        assert tle.mean_motion == 15.49309239
        assert tle.period_minutes == pytest.approx(92.68, rel=0.01)

    def test_parse_tle_history_invalid_tle_lines(self, spacetrack_service: SpaceTrackService):
        """Test TLE history parsing with invalid TLE line lengths."""
        invalid_data = [
            {
                "NORAD_CAT_ID": "25544",
                "OBJECT_NAME": "TEST SAT",
                "EPOCH": "2024-06-05T19:58:12.000000",
                "MEAN_MOTION": "15.0",
                "TLE_LINE1": "1 25544U",  # Too short
                "TLE_LINE2": "2 25544",  # Too short
            }
        ]

        result = spacetrack_service._parse_tle_history(invalid_data)
        assert len(result) == 1
        assert result[0].tle_line1 == "1 25544U"

        # TODO ADD Validation of TLE

    def test_parse_tle_history_missing_data(self, spacetrack_service):
        """Test TLE history parsing with missing data."""
        incomplete_data = [
            {
                "NORAD_CAT_ID": "25544",
                "OBJECT_NAME": "TEST SAT",
                # Missing EPOCH and other fields
            }
        ]

        result = spacetrack_service._parse_tle_history(incomplete_data)
        assert len(result) == 1
        tle = result[0]
        assert tle.norad_id == "25544"
        assert tle.mean_motion == 0.0  # Default value
        assert tle.period_minutes is None

        # TODO ADD Validation of TLE

    def test_parse_tle_history_error_handling(self, spacetrack_service):
        """Test TLE history parsing with corrupted data."""
        corrupted_data = [
            {"NORAD_CAT_ID": "25544"},  # Valid entry
            "invalid_data",  # Invalid entry
            {"NORAD_CAT_ID": "25545"},  # Another valid entry
        ]

        result = spacetrack_service._parse_tle_history(corrupted_data)
        assert len(result) == 2
        assert result[0].norad_id == "25544"
        assert result[1].norad_id == "25545"

    def test_calculate_tle_age_recent(self, spacetrack_service: SpaceTrackService):
        """Test TLE age calculation for recent data."""
        with patch("services.spacetrack_service.datetime") as mock_datetime:
            mock_now = datetime(2024, 6, 6, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime = datetime.strptime

            tle_data = {"EPOCH": "2024-06-05T12:00:00.000000"}
            result = spacetrack_service._calculate_tle_age(tle_data)

            assert result["age_days"] == 1
            assert result["is_fresh"]
            assert result["warning"] is None

    def test_calculate_tle_age_old(self, spacetrack_service: SpaceTrackService):
        """Test TLE age calculation for old data."""
        with patch("services.spacetrack_service.datetime") as mock_datetime:
            mock_now = datetime(2024, 6, 20, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime = datetime.strptime

            tle_data = {"EPOCH": "2024-06-05T12:00:00.000000"}
            result = spacetrack_service._calculate_tle_age(tle_data)

            assert result["age_days"] == 15
            assert not result["is_fresh"]
            assert result["warning"] == "TLE is outdated"

    def test_calculate_tle_age_no_epoch(self, spacetrack_service: SpaceTrackService):
        """Test TLE age calculation without epoch."""
        tle_data: dict[str, Any] = {}

        with pytest.raises(Exception, match="No epoch data"):
            spacetrack_service._calculate_tle_age(tle_data)

    def test_parse_epoch_date_success(self, spacetrack_service: SpaceTrackService):
        """Test successful epoch parsing."""
        test_cases = [
            "2024-06-05T19:58:12.000000",
            "2024-06-05T19:58:12",
            "2024-06-05 19:58:12.000000",
            "2024-06-05 19:58:12",
        ]

        for epoch_str in test_cases:
            result = spacetrack_service._parse_epoch_date(epoch_str)
            assert isinstance(result, datetime)
            assert result.year == 2024
            assert result.month == 6
            assert result.day == 5

    def test_parse_epoch_date_invalid(self, spacetrack_service: SpaceTrackService):
        """Test epoch parsing with invalud format."""
        with pytest.raises(ValueError, match="Could not parse epoch"):
            spacetrack_service._parse_epoch_date("invalid-date-format")

    def test_safe_float_valid(self):
        """Test safe float conversion with valid values."""
        assert SpaceTrackService._safe_float("15.5") == 15.5
        assert SpaceTrackService._safe_float(15.5) == 15.5
        assert SpaceTrackService._safe_float(None) == 0.0
        assert SpaceTrackService._safe_float("") == 0.0
        assert SpaceTrackService._safe_float("invalid", 99.9) == 99.9

    def test_safe_int_valid(self):
        """Test safe int conversion with valid values."""
        assert SpaceTrackService._safe_int("15") == 15
        assert SpaceTrackService._safe_int(15) == 15
        assert SpaceTrackService._safe_int(None) == 0
        assert SpaceTrackService._safe_int("") == 0
        assert SpaceTrackService._safe_int("invalid", 99) == 99

    def test_destructor(self, spacetrack_service: SpaceTrackService):
        """Test proper cleanup in destructor."""
        mock_session = Mock()
        spacetrack_service.session = mock_session

        spacetrack_service.__del__()

        mock_session.close.assert_called_once()

    def test_destructor_no_session(self, spacetrack_service: SpaceTrackService):
        """Test destructor when no session exists."""

        spacetrack_service.session = None

        spacetrack_service.__del__()  # should not raise error


class TestSpaceTrackServiceIntegration:
    """Integration tests for SpaceTrackService."""

    @patch.object(SpaceTrackService, "authenticate")
    @patch.object(SpaceTrackService, "_ensure_authenticated")
    def test_full_tle_history_workflow(
        self,
        mock_ensure_auth,
        mock_authenticate,
        spacetrack_service,
        sample_spacetrack_history_response,
    ):
        mock_authenticate.return_value = True
        mock_session = Mock()
        mock_ensure_auth.return_value = mock_session

        mock_response = Mock()
        mock_response.json.return_value = sample_spacetrack_history_response
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        result = spacetrack_service.fetch_tle_history("25544", 7)

        assert len(result) == 2
        assert all(isinstance(tle, TLEData) for tle in result)

        assert result[0].element_set_no == 999
        assert result[1].element_set_no == 998

    @patch.object(SpaceTrackService, "authenticate")
    @patch.object(SpaceTrackService, "_ensure_authenticated")
    def test_full_age_info_workflow(
        self,
        mock_ensure_auth,
        mock_authenticate,
        spacetrack_service,
        sample_spacetrack_age_response,
    ):
        """Test complete TLE age info workflow."""
        mock_authenticate.return_value = True
        mock_session = Mock()
        mock_ensure_auth.return_value = mock_session

        mock_response = Mock()
        mock_response.json.return_value = sample_spacetrack_age_response
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        with patch("services.spacetrack_service.datetime") as mock_datetime:
            mock_now = datetime(2024, 6, 6, 19, 58, 12)
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime = datetime.strptime

            result = spacetrack_service.get_latest_tle_age("25544")

        assert result["age_days"] == 1
        assert result["is_fresh"]
        assert "epoch" in result

    def test_error_propagation(self, spacetrack_service):
        """Test that errors are properly propagated."""
        with patch.object(spacetrack_service, "authenticate", return_value=False):
            with pytest.raises(Exception, match="Authentication failed"):
                spacetrack_service.fetch_tle_history("25544", 30)

    @pytest.mark.slow
    def test_multiple_requests_performance(self, spacetrack_service: SpaceTrackService):
        """Test performance with multiple requests."""
        with patch.object(spacetrack_service, "_ensure_authenticated") as mock_ensure_auth:
            mock_session = Mock()
            mock_ensure_auth.return_value = mock_session

            mock_response = Mock()
            mock_response.json.return_value = []
            mock_response.raise_for_status.return_value = None
            mock_session.get.return_value = mock_response

            for i in range(10):
                result = spacetrack_service.fetch_tle_history(f"2554{i}", 30)
                assert result == []

            assert mock_ensure_auth.call_count == 10

    def test_date_range_calculation(self, spacetrack_service: SpaceTrackService):
        """Test that date ranges are calculated correctly."""
        with patch.object(spacetrack_service, "_ensure_authenticated") as mock_ensure_auth:
            mock_session = Mock()
            mock_ensure_auth.return_value = mock_session

            mock_response = Mock()
            mock_response.json.return_value = []
            mock_response.raise_for_status.return_value = None
            mock_session.get.return_value = mock_response

            with patch("services.spacetrack_service.datetime") as mock_datetime:
                mock_now = datetime(2024, 6, 10, 12, 0, 0)
                mock_datetime.now.return_value = mock_now
                mock_datetime.strftime = datetime.strftime

                spacetrack_service.fetch_tle_history("25544", 7)

        call_args = mock_session.get.call_args[0][0]
        assert "2024-06-03--2024-06-10" in call_args

    def test_url_construction(self, spacetrack_service: SpaceTrackService):
        """Test that URLs are constructed correctly."""
        with patch.object(spacetrack_service, "_ensure_authenticated") as mock_ensure_auth:
            mock_session = Mock()
            mock_ensure_auth.return_value = mock_session

            history_response = Mock()
            history_response.json.return_value = []
            history_response.raise_for_status.return_value = None

            age_response = Mock()
            age_response.json.return_value = [{"NORAD_CAT_ID": "25544", "EPOCH": "2024-06-05T19:58:12.000000"}]
            age_response.raise_for_status.return_value = None

            mock_session.get.side_effect = [history_response, age_response]

            spacetrack_service.fetch_tle_history("25544", 30)
            history_call = mock_session.get.call_args_list[0]
            history_url = history_call[0][0]

            assert spacetrack_service.base_url in history_url
            assert "class/tle/" in history_url
            assert "NORAD_CAT_ID/25544" in history_url
            assert "format/json" in history_url
            assert "orderby/TLE_LINE1%20desc" in history_url

            spacetrack_service.get_latest_tle_age("25544")
            age_call = mock_session.get.call_args_list[1]
            age_url = age_call[0][0]

            assert spacetrack_service.base_url in age_url
            assert "class/tle_latest/" in age_url
            assert "NORAD_CAT_ID/25544" in age_url
            assert "format/json" in age_url


class TestSpaceTrackServiceEdgeCases:
    """Edge case tests for SpaceTrackService."""

    def test_very_old_tle_data(self, spacetrack_service):
        """Test handling of very old TLE data."""
        old_data = [
            {
                "NORAD_CAT_ID": "25544",
                "OBJECT_NAME": "ISS (ZARYA)",
                "EPOCH": "2020-01-01T00:00:00.000000",
                "MEAN_MOTION": "15.0",
                "TLE_LINE1": "1 25544U 98067A   20001.00000000  .00002182  00000+0  40768-4 0  9990",
                "TLE_LINE2": "2 25544  51.6461 339.7939 0001220  92.8340 267.3124 15.00000000456831",
            }
        ]

        result = spacetrack_service._parse_tle_history(old_data)
        assert len(result) == 1
        assert result[0].epoch == "2020-01-01T00:00:00.000000"

    def test_zero_mean_motion(self, spacetrack_service):
        """Test handling of zero mean motion."""
        zero_motion_data = [
            {
                "NORAD_CAT_ID": "25544",
                "OBJECT_NAME": "TEST SAT",
                "EPOCH": "2024-06-05T19:58:12.000000",
                "MEAN_MOTION": "0.0",
                "TLE_LINE1": "1 25544U 98067A   24157.83208333  .00002182  00000+0  40768-4 0  9990",
                "TLE_LINE2": "2 25544  51.6461 339.7939 0001220  92.8340 267.3124 0.00000000456831",
            }
        ]

        result = spacetrack_service._parse_tle_history(zero_motion_data)
        assert len(result) == 1
        assert result[0].mean_motion == 0.0
        assert result[0].period_minutes is None

    def test_missing_optional_fields(self, spacetrack_service):
        """Test handling of missing optional fields."""
        minimal_data = [
            {
                "NORAD_CAT_ID": "25544",
                "OBJECT_NAME": "TEST SAT",
                "TLE_LINE1": "1 25544U 98067A   24157.83208333  .00002182  00000+0  40768-4 0  9990",
                "TLE_LINE2": "2 25544  51.6461 339.7939 0001220  92.8340 267.3124 15.49309239456831",
            }
        ]

        result = spacetrack_service._parse_tle_history(minimal_data)
        assert len(result) == 1
        tle = result[0]
        assert tle.norad_id == "25544"
        assert tle.satellite_name == "TEST SAT"
        assert tle.epoch == ""  # Default value
        assert tle.classification is None

    def test_large_dataset_processing(self, spacetrack_service):
        """Test processing of large datasets."""
        # Create large dataset
        large_data = []
        for i in range(100):
            entry = {
                "NORAD_CAT_ID": "25544",
                "OBJECT_NAME": f"TEST SAT {i}",
                "EPOCH": f"2024-06-{5 + (i % 25):02d}T19:58:12.000000",
                "MEAN_MOTION": f"{15.0 + (i * 0.01)}",
                "TLE_LINE1": f"1 25544U 98067A   24157.83208333  .00002182  00000+0  40768-4 0  999{i % 10}",
                "TLE_LINE2": f"2 25544  51.6461 339.7939 0001220  92.8340 267.3124 {15.0 + (i * 0.01):.8f}45683{i % 10}",
            }
            large_data.append(entry)

        result = spacetrack_service._parse_tle_history(large_data)
        assert len(result) == 100
        assert all(isinstance(tle, TLEData) for tle in result)
