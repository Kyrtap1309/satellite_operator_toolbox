import json
from datetime import datetime

from flask import Flask, render_template, request

from config import Config
from models.satellite import GroundStation
from services.celestrak_service import CelestrakService
from services.satellite_service import SatelliteService
from services.spacetrack_service import SpaceTrackService
from services.tle_input_service import TLEInputService
from utils.formatters import DataFormatter
from utils.logging_config import setup_logging
from utils.route_decorators import (
    handle_calculation_errors,
    handle_route_errors,
    log_route_access,
)


def create_app():
    """Application factory."""
    app = Flask(__name__)

    # Load configuration
    config = Config()

    app.secret_key = config.SECRET_KEY

    # Setup logging
    setup_logging(app, config)

    # Initialize services
    spacetrack_service = SpaceTrackService(config)
    celestrak_service = CelestrakService(config)
    satellite_service = SatelliteService(spacetrack_service, celestrak_service)

    # Register routes
    register_routes(app, config, satellite_service)
    register_error_handlers(app)

    return app


def register_routes(app, config: Config, satellite_service: SatelliteService):
    """Register application routes."""

    # Create TLE input service instance
    tle_input_service = TLEInputService(satellite_service)

    @app.route("/")
    @log_route_access()
    def index():
        """Render the main index page."""
        return render_template("index.html")

    @app.route("/satellite_passes")
    @log_route_access()
    def satellite_passes():
        """Render the satellite passes calculator page."""
        return render_template(
            "satellite_passes/index.html",
            tle_name=config.SATELLITE_NAME,
            tle_line1=config.SATELLITE_TLE_LINE1,
            tle_line2=config.SATELLITE_TLE_LINE2,
            gs1_name=config.STATION1_NAME,
            gs1_lat=config.STATION1_LAT,
            gs1_lon=config.STATION1_LON,
            gs1_elev=config.STATION1_ELEV,
            gs2_name=config.STATION2_NAME,
            gs2_lat=config.STATION2_LAT,
            gs2_lon=config.STATION2_LON,
            gs2_elev=config.STATION2_ELEV,
            min_el=config.MIN_ELEVATION,
        )

    @app.route("/calculate", methods=["POST"])
    @handle_calculation_errors("satellite_passes")
    @log_route_access()
    def calculate():
        """Calculate satellite passes for two ground stations."""
        app.logger.info("Pass calculation requested")

        # Get TLE data using the service
        tle_data = tle_input_service.get_tle_data(request.form)

        # Parse form data
        form_data = request.form

        gs1 = GroundStation(
            name=form_data.get("gs1_name", config.STATION1_NAME),
            latitude=float(form_data.get("gs1_lat", config.STATION1_LAT)),
            longitude=float(form_data.get("gs1_lon", config.STATION1_LON)),
            elevation=float(form_data.get("gs1_elev", config.STATION1_ELEV)),
        )

        gs2 = GroundStation(
            name=form_data.get("gs2_name", config.STATION2_NAME),
            latitude=float(form_data.get("gs2_lat", config.STATION2_LAT)),
            longitude=float(form_data.get("gs2_lon", config.STATION2_LON)),
            elevation=float(form_data.get("gs2_elev", config.STATION2_ELEV)),
        )

        min_el = float(form_data.get("min_el", config.MIN_ELEVATION))
        date = form_data.get("date")

        start_time = datetime.strptime(f"{date} 00:00:00", "%Y-%m-%d %H:%M:%S")
        end_time = datetime.strptime(f"{date} 23:59:59", "%Y-%m-%d %H:%M:%S")

        app.logger.info(f"Calculating passes for {tle_data.satellite_name} on {date}")

        # Find passes
        passes_gs1 = satellite_service.find_passes(
            tle_data, gs1, start_time, end_time, min_el
        )
        passes_gs2 = satellite_service.find_passes(
            tle_data, gs2, start_time, end_time, min_el
        )
        common_windows = satellite_service.find_common_windows(passes_gs1, passes_gs2)

        # Format data
        formatter = DataFormatter()
        formatted_gs1 = formatter.format_passes_for_display(passes_gs1)
        formatted_gs2 = formatter.format_passes_for_display(passes_gs2)
        formatted_common = formatter.format_common_windows(common_windows)
        timeline_data = formatter.prepare_timeline_data(
            passes_gs1, passes_gs2, common_windows, gs1.name, gs2.name
        )

        app.logger.info(
            f"Calculation completed. Found {len(formatted_common)} common windows"
        )

        return render_template(
            "satellite_passes/results.html",
            gs1_name=gs1.name,
            gs2_name=gs2.name,
            gs1_passes=formatted_gs1,
            gs2_passes=formatted_gs2,
            common_windows=formatted_common,
            timeline_data=json.dumps(timeline_data),
            date=date,
            gs1_lat=gs1.latitude,
            gs1_lon=gs1.longitude,
            gs1_elev=gs1.elevation,
            gs2_lat=gs2.latitude,
            gs2_lon=gs2.longitude,
            gs2_elev=gs2.elevation,
        )

    @app.route("/satellite_position")
    @log_route_access()
    def satellite_position():
        """Render the satellite position calculator page."""
        now = datetime.now()
        default_date = now.strftime("%Y-%m-%d")
        default_time = now.strftime("%H:%M")

        return render_template(
            "satellite_position/position_calculator.html",
            tle_name=config.SATELLITE_NAME,
            tle_line1=config.SATELLITE_TLE_LINE1,
            tle_line2=config.SATELLITE_TLE_LINE2,
            norad_id="",
            default_date=default_date,
            default_time=default_time,
        )

    @app.route("/calculate_position", methods=["POST"])
    @handle_calculation_errors("satellite_position", preserve_form_data=True)
    @log_route_access()
    def calculate_position():
        """Calculate satellite position at a specific time."""
        # Get TLE data using the service
        tle_data = tle_input_service.get_tle_data(request.form)

        # Get date and time
        date_str = request.form.get("date")
        time_str = request.form.get("time")

        # Parse date and time - handle seconds format
        if len(time_str.split(":")) == 3:  # HH:MM:SS format
            time_obj = datetime.strptime(time_str, "%H:%M:%S").time()
        else:  # HH:MM format
            time_obj = datetime.strptime(time_str, "%H:%M").time()

        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        calculation_time = datetime.combine(date_obj, time_obj)

        app.logger.info(
            f"Calculating position for {tle_data.satellite_name} at {calculation_time}"
        )

        # Calculate position
        position = satellite_service.calculate_position(tle_data, calculation_time)

        input_method = request.form.get("input_method", "norad")
        return render_template(
            "satellite_position/position_calculator.html",
            tle_name=tle_data.satellite_name if input_method == "tle" else "",
            tle_line1=tle_data.tle_line1 if input_method == "tle" else "",
            tle_line2=tle_data.tle_line2 if input_method == "tle" else "",
            norad_id=request.form.get("norad_id") if input_method == "norad" else "",
            default_date=date_str,
            default_time=time_str,
            position_data=position,
        )

    @app.route("/tle_viewer")
    @log_route_access()
    def tle_viewer():
        """Render the TLE viewer page."""
        return render_template("tle/tle_viewer.html")

    @app.route("/fetch_tle_data", methods=["POST"])
    @handle_route_errors("tle_viewer")
    @log_route_access()
    def fetch_tle_data():
        """Fetch TLE data and history for a satellite."""
        norad_id = request.form.get("norad_id", "").strip()
        days_back = int(request.form.get("days_back", 30))

        if not norad_id:
            raise ValueError("Please provide a NORAD ID")

        app.logger.info(f"TLE data fetch requested for NORAD ID: {norad_id}")

        # Get current TLE
        try:
            current_tle = satellite_service.get_current_tle(norad_id)
        except Exception as e:
            app.logger.error(f"Error fetching current TLE: {e}")
            current_tle = {"error": str(e)}

        # Get TLE history
        try:
            tle_history = satellite_service.get_tle_history(norad_id, days_back)
        except Exception as e:
            app.logger.error(f"Error fetching TLE history: {e}")
            tle_history = []

        # Get TLE age info
        try:
            tle_age_info = satellite_service.get_tle_age_info(norad_id)
        except Exception as e:
            app.logger.error(f"Error fetching TLE age info: {e}")
            tle_age_info = {"error": str(e)}

        return render_template(
            "tle/tle_viewer.html",
            norad_id=norad_id,
            days_back=days_back,
            current_tle=current_tle,
            tle_history=tle_history,
            tle_age_info=tle_age_info,
        )

    @app.route("/import_tle/<norad_id>")
    @handle_route_errors("index")
    @log_route_access()
    def import_tle(norad_id):
        """Import TLE data for a satellite by NORAD ID."""
        app.logger.info(f"TLE import requested for NORAD ID: {norad_id}")

        tle_data = satellite_service.get_current_tle(norad_id)

        return render_template(
            "satellite_passes/index.html",
            tle_name=tle_data.satellite_name,
            tle_line1=tle_data.tle_line1,
            tle_line2=tle_data.tle_line2,
            norad_id=norad_id,
            gs1_name=config.STATION1_NAME,
            gs1_lat=config.STATION1_LAT,
            gs1_lon=config.STATION1_LON,
            gs1_elev=config.STATION1_ELEV,
            gs2_name=config.STATION2_NAME,
            gs2_lat=config.STATION2_LAT,
            gs2_lon=config.STATION2_LON,
            gs2_elev=config.STATION2_ELEV,
            min_el=config.MIN_ELEVATION,
        )

    @app.route("/search_satellites", methods=["GET"])
    @handle_route_errors("tle_viewer")
    @log_route_access()
    def search_satellites():
        """Search for satellites by name or NORAD ID."""
        query = request.args.get("query", "").strip()
        if not query:
            raise ValueError("Please provide a search query")

        app.logger.info(f"Satellite search requested: {query}")

        results = satellite_service.search_satellites(query)
        return render_template(
            "tle_viewer/search_results.html", results=results, query=query
        )


def register_error_handlers(app):
    """Register error handlers."""

    @app.errorhandler(404)
    def not_found_error(error):
        app.logger.warning(f"404 error: {request.url}")
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"500 error: {error}")
        return render_template("500.html"), 500


if __name__ == "__main__":
    app = create_app()
    config = Config()
    app.logger.info("Starting Satellite Operator Application")
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG)
