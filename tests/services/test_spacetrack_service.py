from unittest.mock import Mock, patch

import pytest
from requests.exceptions import HTTPError

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
    def test_authenticate_success(
        self, mock_session_class, spacetrack_service: SpaceTrackService
    ):
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
    def test_authenticate_login_failure(
        self, mock_session_class, spacetrack_service: SpaceTrackService
    ):
        """Test authentication failure durign login."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_session.post.side_effect = HTTPError("Login failed")

        result = spacetrack_service.authenticate()

        assert not result
        assert spacetrack_service.session is None

    @patch("services.spacetrack_service.requests.Session")
    def test_authenticate_test_failure(
        self, mock_session_class, spacetrack_service: SpaceTrackService
    ):
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
    def test_fetch_tle_history_empty_response(
        self, mock_ensure_auth, spacetrack_service: SpaceTrackService
    ):
        """Test TLE history fetch with empty response."""
        mock_session = Mock()
        mock_ensure_auth.return_value = mock_session

        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        result = spacetrack_service.fetch_tle_history("999999", 30)

        assert result == []
