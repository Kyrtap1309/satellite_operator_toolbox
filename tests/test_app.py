from unittest.mock import Mock, patch

import pytest
from flask import Flask

from app import create_app, register_error_handlers, register_routes
from config import Config


class TestCreateApp:
    """Test cases for application factory."""

    @patch("app.SatelliteService")
    @patch("app.CelestrakService")
    @patch("app.SpaceTrackService")
    @patch("app.setup_logging")
    def test_create_app_success(
        self, mock_setup_logging, mock_spacetrack, mock_celestrak, mock_satellite
    ):
        """Test successful application creation."""

        with patch("app.Config") as mock_config_class:
            mock_config = Mock()
            mock_config.SECRET_KEY = "test-secret-key"
            mock_config_class.return_value = mock_config

            app = create_app()

        assert isinstance(app, Flask)
        assert app.secret_key == "test-secret-key"
        mock_setup_logging.assert_called_once()
        mock_spacetrack.assert_called_once_with(mock_config)
        mock_celestrak.assert_called_once_with(mock_config)

    @patch("app.register_error_handlers")
    @patch("app.register_routes")
    @patch("app.SatelliteService")
    @patch("app.CelestrakService")
    @patch("app.SpaceTrackService")
    @patch("app.setup_logging")
    def test_create_app_registers_components(
        self,
        mock_setup_logging,
        mock_spacetrack,
        mock_celestrak,
        mock_satellite,
        mock_register_routes,
        mock_register_error_handlers,
    ):
        """Test that app creation registers all components."""
        with patch("app.Config"):
            create_app()

        mock_register_routes.assert_called_once()
        mock_register_error_handlers.assert_called_once()


class TestRegisterRoutes:
    """Test cases for route registration."""

    @pytest.fixture
    def app(self):
        """Create testFlask app."""
        return Flask(__name__)

    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        config = Mock(spec=Config)
        config.SATELLITE_NAME = "ISS (ZARYA)"
        config.SATELLITE_TLE_LINE1 = (
            "1 25544U 98067A   24157.83208333  .00002182  00000+0  40768-4 0  9990"
        )
        config.SATELLITE_TLE_LINE2 = (
            "2 25544  51.6461 339.7939 0001220  92.8340 267.3124 15.49309239456831"
        )
        config.STATION1_NAME = "Station 1"
        config.STATION1_LAT = 52.0
        config.STATION1_LON = 21.0
        config.STATION1_ELEV = 100.0
        config.STATION2_NAME = "Station 2"
        config.STATION2_LAT = 51.0
        config.STATION2_LON = 20.0
        config.STATION2_ELEV = 150.0
        config.MIN_ELEVATION = 10.0
        return config

    @pytest.fixture
    def mock_satellite_service(self):
        """Mock satellite service."""
        return Mock()

    def test_register_routes_success(self, app, mock_config, mock_satellite_service):
        """Test successful route registration."""
        with app.app_context():
            register_routes(app, mock_config, mock_satellite_service)

        routes = [rule.rule for rule in app.url_map.iter_rules()]
        expected_routes = [
            "/",
            "/satellite_passes",
            "/calculate",
            "/satellite_position",
            "/calculate_position",
            "/tle_viewer",
            "/import_tle/<norad_id>",
            "/search_satellites",
        ]

        for route in expected_routes:
            assert route in routes


class TestRoutes:
    """Test cases for individual routes."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        with (
            patch("app.Config") as mock_config_class,
            patch("app.setup_logging"),
            patch("app.SpaceTrackService"),
            patch("app.CelestrakService"),
            patch("app.SatelliteService"),
            patch("app.render_template") as mock_render,
        ):
            # Mock render_template to avoid template loading issues
            mock_render.return_value = "<html>Test Response</html>"

            mock_config = Mock()
            mock_config.SECRET_KEY = "test-secret"
            mock_config.SATELLITE_NAME = "ISS (ZARYA)"
            mock_config.SATELLITE_TLE_LINE1 = "test line 1"
            mock_config.SATELLITE_TLE_LINE2 = "test line 2"
            mock_config.STATION1_NAME = "Station 1"
            mock_config.STATION1_LAT = 52.0
            mock_config.STATION1_LON = 21.0
            mock_config.STATION1_ELEV = 100.0
            mock_config.STATION2_NAME = "Station 2"
            mock_config.STATION2_LAT = 51.0
            mock_config.STATION2_LON = 20.0
            mock_config.STATION2_ELEV = 150.0
            mock_config.MIN_ELEVATION = 10.0
            mock_config_class.return_value = mock_config

            app = create_app()
            app.config["TESTING"] = True
            with app.test_client() as client:
                yield client

    def test_index_route(self, client):
        """Test index route."""
        response = client.get("/")
        assert response.status_code == 200

    def test_satellite_passes_route(self, client):
        """Test satellite passes route."""
        response = client.get("/satellite_passes")
        assert response.status_code == 200

    def test_satellite_position_route(self, client):
        """Test satellite position route."""
        response = client.get("/satellite_position")
        assert response.status_code == 200

    def test_tle_viewer_route(self, client):
        """Test TLE viewer route."""
        response = client.get("/tle_viewer")
        assert response.status_code == 200

    def test_search_satellites_route_no_query(self, client):
        """Test search satellites route without query."""
        response = client.get("/search_satellites")
        # Error handler redirects to tle_viewer route, so we get 302
        assert response.status_code == 302
        # Check that it redirects to the expected error page
        assert "/tle_viewer" in response.location

    def test_search_satellites_route_with_query(self, client):
        """Test search satellites route with query."""
        with patch("app.SatelliteService") as mock_service_class:
            # Mock the service instance that gets created in create_app
            mock_service = Mock()
            mock_service.search_satellites.return_value = []
            mock_service_class.return_value = mock_service

            response = client.get("/search_satellites?query=ISS")
            assert response.status_code == 200


class TestErrorHandlers:
    """Test cases for error handlers."""

    def test_register_error_handlers(self):
        """Test error handler registration."""
        app = Flask(__name__)
        register_error_handlers(app)

        # Check that error handlers are registered
        assert 404 in app.error_handler_spec[None]
        assert 500 in app.error_handler_spec[None]

    def test_404_error_handler(self):
        """Test 404 error handler."""
        app = Flask(__name__)
        register_error_handlers(app)

        with patch("app.render_template") as mock_render:
            mock_render.return_value = "<html>404 Error</html>"

            with app.test_client() as client:
                response = client.get("/nonexistent-route")
                assert response.status_code == 404

    def test_500_error_handler(self):
        """Test 500 error handler."""
        app = Flask(__name__)
        register_error_handlers(app)

        @app.route("/test-error")
        def test_error():
            raise Exception("Test error")

        with patch("app.render_template") as mock_render:
            mock_render.return_value = "<html>500 Error</html>"

            with app.test_client() as client:
                response = client.get("/test-error")
                assert response.status_code == 500


class TestCalculateRoute:
    """Test cases for calculate route."""

    @pytest.fixture
    def client_with_mocks(self):
        """Create test client with mocked services."""
        with (
            patch("app.Config") as mock_config_class,
            patch("app.setup_logging"),
            patch("app.SpaceTrackService"),
            patch("app.CelestrakService"),
            patch("app.SatelliteService") as mock_satellite_service,
            patch("app.render_template") as mock_render,
        ):
            # Mock render_template to avoid template loading issues
            mock_render.return_value = "<html>Test Response</html>"

            # Setup config mock
            mock_config = Mock()
            mock_config.SECRET_KEY = "test-secret"
            mock_config.STATION1_NAME = "Station 1"
            mock_config.STATION1_LAT = 52.0
            mock_config.STATION1_LON = 21.0
            mock_config.STATION1_ELEV = 100.0
            mock_config.STATION2_NAME = "Station 2"
            mock_config.STATION2_LAT = 51.0
            mock_config.STATION2_LON = 20.0
            mock_config.STATION2_ELEV = 150.0
            mock_config.MIN_ELEVATION = 10.0
            mock_config_class.return_value = mock_config

            # Setup satellite service mock
            mock_service = Mock()
            mock_satellite_service.return_value = mock_service

            app = create_app()
            app.config["TESTING"] = True

            with app.test_client() as client:
                yield client, mock_service

    def test_calculate_get_method_not_allowed(self, client_with_mocks):
        """Test that GET requests to calculate route are not allowed."""
        client, _ = client_with_mocks
        response = client.get("/calculate")
        assert response.status_code == 405

    def test_calculate_post_missing_data(self, client_with_mocks):
        """Test calculate POST with missing form data."""
        client, _ = client_with_mocks

        # Send POST request with incomplete data
        response = client.post("/calculate", data={})

        # Should redirect due to error handler
        assert response.status_code == 302


class TestImportTleRoute:
    """Test cases for import TLE route."""

    @pytest.fixture
    def client_with_mocks(self):
        """Create test client with mocked services."""
        with (
            patch("app.Config") as mock_config_class,
            patch("app.setup_logging"),
            patch("app.SpaceTrackService"),
            patch("app.CelestrakService"),
            patch("app.SatelliteService") as mock_satellite_service,
            patch("app.render_template") as mock_render,
        ):
            # Mock render_template to avoid template loading issues
            mock_render.return_value = "<html>Test Response</html>"

            mock_config = Mock()
            mock_config.SECRET_KEY = "test-secret"
            mock_config.STATION1_NAME = "Station 1"
            mock_config.STATION1_LAT = 52.0
            mock_config.STATION1_LON = 21.0
            mock_config.STATION1_ELEV = 100.0
            mock_config.STATION2_NAME = "Station 2"
            mock_config.STATION2_LAT = 51.0
            mock_config.STATION2_LON = 20.0
            mock_config.STATION2_ELEV = 150.0
            mock_config.MIN_ELEVATION = 10.0
            mock_config_class.return_value = mock_config

            mock_service = Mock()
            mock_satellite_service.return_value = mock_service

            app = create_app()
            app.config["TESTING"] = True

            with app.test_client() as client:
                yield client, mock_service

    def test_import_tle_success(self, client_with_mocks, sample_tle_data):
        """Test successful TLE import."""
        client, mock_service = client_with_mocks

        mock_service.get_current_tle.return_value = sample_tle_data

        response = client.get("/import_tle/25544")
        assert response.status_code == 200
        mock_service.get_current_tle.assert_called_once_with("25544")

    def test_import_tle_service_error(self, client_with_mocks):
        """Test TLE import with service error."""
        client, mock_service = client_with_mocks

        # Configure the mock service to raise an exception
        mock_service.get_current_tle.side_effect = Exception("TLE not found")

        with pytest.raises(Exception, match="TLE not found"):
            client.get("/import_tle/25544")

        # Verify the service method was called with correct parameter
        mock_service.get_current_tle.assert_called_once_with("25544")


class TestAppIntegration:
    """Integration tests for the application."""

    @pytest.fixture
    def app_with_mocks(self):
        """Create app with mocked dependencies."""
        with (
            patch("app.Config") as mock_config_class,
            patch("app.setup_logging"),
            patch("app.SpaceTrackService"),
            patch("app.CelestrakService"),
            patch("app.SatelliteService"),
            patch("app.render_template") as mock_render,
        ):
            # Mock render_template to avoid template loading issues
            mock_render.return_value = "<html>Test Response</html>"

            mock_config = Mock()
            mock_config.SECRET_KEY = "test-secret"
            mock_config.SATELLITE_NAME = "ISS"
            mock_config.SATELLITE_TLE_LINE1 = "test line 1"
            mock_config.SATELLITE_TLE_LINE2 = "test line 2"
            mock_config.STATION1_NAME = "Station 1"
            mock_config.STATION1_LAT = 52.0
            mock_config.STATION1_LON = 21.0
            mock_config.STATION1_ELEV = 100.0
            mock_config.STATION2_NAME = "Station 2"
            mock_config.STATION2_LAT = 51.0
            mock_config.STATION2_LON = 20.0
            mock_config.STATION2_ELEV = 150.0
            mock_config.MIN_ELEVATION = 10.0
            mock_config_class.return_value = mock_config

            app = create_app()
            app.config["TESTING"] = True
            yield app

    def test_app_startup_and_routes(self, app_with_mocks):
        """Test that app starts and routes are accessible."""
        with app_with_mocks.test_client() as client:
            # Test main routes
            routes_to_test = [
                "/",
                "/satellite_passes",
                "/satellite_position",
                "/tle_viewer",
            ]

            for route in routes_to_test:
                response = client.get(route)
                assert response.status_code == 200

    def test_app_error_handling(self, app_with_mocks):
        """Test application error handling."""
        with app_with_mocks.test_client() as client:
            # Test 404 handling
            response = client.get("/nonexistent")
            assert response.status_code == 404
