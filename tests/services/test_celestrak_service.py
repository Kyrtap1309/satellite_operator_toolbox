from unittest.mock import Mock, patch

import pytest
from requests.exceptions import HTTPError, RequestException, Timeout

from config import Config
from models.satellite import TLEData
from services.celestrak_service import CelestrakService


class TestCelestrakService:
    """Test cases for CelstrakService."""

    def test_init(self, mock_config: Config):
        """Test service initialization."""
        service = CelestrakService(mock_config)

        assert service.config == mock_config
        assert service.base_url == mock_config.CELESTRAK_BASE_URL
        assert service.logger is not None

    @patch("services.celestrak_service.requests.get")
    def test_fetch_current_tle_success(
        self,
        mock_get,
        celestrak_service: CelestrakService,
        sample_json_response,
        sample_tle_response,
        sample_tle_data,
    ):
        """Test successful TLE fetch."""

        json_response = Mock()
        json_response.json.return_value = sample_json_response
        json_response.raise_for_status.return_value = None

        tle_response = Mock()
        tle_response.text = sample_tle_response
        tle_response.raise_for_status.return_value = None

        mock_get.side_effect = [json_response, tle_response]

        result = celestrak_service.fetch_current_tle("25544")

        assert isinstance(result, TLEData)
        assert result.norad_id == "25544"
        assert result.satellite_name == "ISS (ZARYA)"
        assert result.tle_line1.startswith("1 25544U")
        assert result.tle_line2.startswith("2 25544")
        assert result.mean_motion == 15.49309239
        assert result.period_minutes == pytest.approx(92.68, rel=0.01)

        assert mock_get.call_count == 2
        json_call = mock_get.call_args_list[0]
        tle_call = mock_get.call_args_list[1]

        assert "FORMAT=json" in json_call[0][0]
        assert "FORMAT=TLE" in tle_call[0][0]
        assert "CATNR=25544" in json_call[0][0]
        assert "CATNR=25544" in tle_call[0][0]

    @patch("services.celestrak_service.requests.get")
    def test_fetch_json_data_success(self, mock_get, celestrak_service: CelestrakService, sample_json_response):
        """Test successful JSON data fetch."""
        mock_response = Mock()
        mock_response.json.return_value = sample_json_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = celestrak_service._fetch_json_data("25544")

        assert result == sample_json_response[0]
        mock_get.assert_called_once()
        assert "FORMAT=json" in mock_get.call_args[0][0]

    @patch("services.celestrak_service.requests.get")
    def test_fetch_json_data_empty_response(self, mock_get, celestrak_service: CelestrakService):
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        with pytest.raises(Exception, match="No satellite data found"):
            celestrak_service._fetch_json_data("99999999")

    @patch("services.celestrak_service.requests.get")
    def test_fetch_json_data_http_error(self, mock_get, celestrak_service: CelestrakService):
        """Test JSON fetch with HTTP error."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        with pytest.raises(HTTPError):
            celestrak_service._fetch_json_data("999999")

    @patch("services.celestrak_service.requests.get")
    def test_fetch_json_data_timeout(self, mock_get, celestrak_service):
        mock_get.side_effect = Timeout()
        with pytest.raises(Timeout):
            celestrak_service._fetch_json_data("25544")

    @patch("services.celestrak_service.requests.get")
    def test_fetch_tle_lines_success(self, mock_get, celestrak_service, sample_tle_response):
        """Test successful TLE lines fetch."""
        mock_response = Mock()
        mock_response.text = sample_tle_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = celestrak_service._fetch_tle_lines("25544")

        expected = {
            "satellite_name": "ISS (ZARYA)",
            "tle_line1": "1 25544U 98067A   24157.83208333  .00002182  00000+0  40768-4 0  9990",
            "tle_line2": "2 25544  51.6461 339.7939 0001220  92.8340 267.3124 15.49309239456831",
        }

        assert result == expected
        mock_get.assert_called_once()
        assert "FORMAT=TLE" in mock_get.call_args[0][0]

    @patch("services.celestrak_service.requests.get")
    def test_fetch_tle_lines_empty_response(self, mock_get, celestrak_service: CelestrakService):
        """Test TLE lines fetch with empty response."""
        mock_response = Mock()
        mock_response.text = ""
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        with pytest.raises(Exception, match="No TLE data found"):
            celestrak_service._fetch_tle_lines("999999999999")

    @patch("services.celestrak_service.requests.get")
    def test_fetch_tle_lines_invalid_format(self, mock_get, celestrak_service: CelestrakService):
        mock_response = Mock()
        mock_response.text = "ISS (ZARYA)\n1 25544U"  # Only 2 lines instead of 3
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        with pytest.raises(Exception, match="Invalid TLE format"):
            celestrak_service._fetch_tle_lines("25544")

    def test_combine_tle_data(self, celestrak_service: CelestrakService, sample_json_response):
        """Test TLE data combination."""
        json_data = sample_json_response[0]
        tle_lines = {
            "satellite_name": "ISS (ZARYA)",
            "tle_line1": "1 25544U 98067A   24157.83208333  .00002182  00000+0  40768-4 0  9990",
            "tle_line2": "2 25544  51.6461 339.7939 0001220  92.8340 267.3124 15.49309239456831",
        }

        result = celestrak_service._combine_tle_data(json_data, tle_lines)
        assert isinstance(result, TLEData)
        assert result.norad_id == "25544"
        assert result.satellite_name == "ISS (ZARYA)"
        assert result.mean_motion == 15.49309239
        assert result.period_minutes == pytest.approx(92.67, rel=0.01)
        assert result.epoch == "2024-06-05T19:58:12.000Z"

    def test_combine_tle_data_no_mean_motion(self, celestrak_service):
        """Test TLE data combination without mean motion."""
        json_data = {"NORAD_CAT_ID": "25544"}
        tle_lines = {
            "satellite_name": "TEST SAT",
            "tle_line1": "1 25544U",
            "tle_line2": "2 25544",
        }

        result = celestrak_service._combine_tle_data(json_data, tle_lines)

        assert result.period_minutes is None
        assert result.mean_motion == 0.0

    @patch("services.celestrak_service.requests.get")
    def test_fetch_current_tle_error_handling(self, mock_get, celestrak_service: CelestrakService):
        """Test error handling in fetch_current_tle."""
        mock_get.side_effect = RequestException("Network error")

        with pytest.raises(RequestException):
            celestrak_service.fetch_current_tle("25544")

    @patch("services.celestrak_service.requests.get")
    def test_fetch_with_different_norad_ids(
        self,
        mock_get,
        celestrak_service: CelestrakService,
        sample_json_response,
        sample_tle_response,
    ):
        """Test fetching with different NORAD IDs."""

        test_ids = ["25544", "39084", "43013"]

        for norad_id in test_ids:
            json_data = sample_json_response[0].copy()
            json_data["NORAD_CAT_ID"] = norad_id

            tle_lines = sample_tle_response.replace("25544", norad_id)

            json_response = Mock()
            json_response.json.return_value = [json_data]
            json_response.raise_for_status.return_value = None

            tle_response = Mock()
            tle_response.text = tle_lines
            tle_response.raise_for_status.return_value = None

            mock_get.side_effect = [json_response, tle_response]

            result = celestrak_service.fetch_current_tle(norad_id)
            assert result.norad_id == norad_id
            mock_get.reset_mock()


class TestCelestrakServiceIntegration:
    """Integration tests for CelestrakService."""

    @pytest.mark.integration
    @patch("services.celestrak_service.requests.get")
    def test_real_api_call_structure(self, mock_get, celestrak_service):
        """Test that API calls have correct structure (without hitting real API)."""
        # Mock responses
        json_response = Mock()
        json_response.json.return_value = [{"NORAD_CAT_ID": "25544", "MEAN_MOTION": "15.5"}]
        json_response.raise_for_status.return_value = None

        tle_response = Mock()
        tle_response.text = "ISS\n1 25544U\n2 25544"
        tle_response.raise_for_status.return_value = None

        mock_get.side_effect = [json_response, tle_response]

        celestrak_service.fetch_current_tle("25544")

        # Verify correct URLs were called
        calls = mock_get.call_args_list
        assert len(calls) == 2

        json_url = calls[0][0][0]
        tle_url = calls[1][0][0]

        assert "celestrak.org" in json_url
        assert "CATNR=25544" in json_url
        assert "FORMAT=json" in json_url

        assert "celestrak.org" in tle_url
        assert "CATNR=25544" in tle_url
        assert "FORMAT=TLE" in tle_url
