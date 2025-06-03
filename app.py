import json
from datetime import datetime, timedelta

from flask import Flask, jsonify, redirect, render_template, request, url_for

from config import Config
from models.satellite import GroundStation, TLEData
from services.cache_service import CacheService
from services.celestrak_service import CelestrakService
from services.satellite_service import SatelliteService
from services.spacetrack_service import SpaceTrackService
from utils.formatters import DataFormatter
from utils.logging_config import setup_logging


def create_app():
    """Application factory."""
    app = Flask(__name__)

    # Load configuration
    config = Config()

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

    @app.route("/")
    def index():
        """Homepage with tool panel."""
        app.logger.debug("Homepage accessed")
        return render_template("index.html")

    @app.route("/satellite_passes")
    def satellite_passes():
        app.logger.debug("Pass calculator page accessed")
        tomorrow = datetime.now() + timedelta(days=1)
        default_date = tomorrow.strftime("%Y-%m-%d")

        return render_template(
            "satellite_passes/index.html",
            gs1_name=config.STATION1_NAME,
            gs1_lat=config.STATION1_LAT,
            gs1_lon=config.STATION1_LON,
            gs1_elev=config.STATION1_ELEV,
            gs2_name=config.STATION2_NAME,
            gs2_lat=config.STATION2_LAT,
            gs2_lon=config.STATION2_LON,
            gs2_elev=config.STATION2_ELEV,
            min_el=config.MIN_ELEVATION,
            default_date=default_date,
            tle_name=config.SATELLITE_NAME,
            tle_line1=config.SATELLITE_TLE_LINE1,
            tle_line2=config.SATELLITE_TLE_LINE2,
        )

    @app.route("/calculate", methods=["POST"])
    def calculate():
        app.logger.info("Pass calculation requested")

        try:
            # Parse form data
            form_data = request.form

            tle_data = TLEData(
                norad_id="",
                satellite_name=form_data.get("tle_name", config.SATELLITE_NAME),
                tle_line1=form_data.get("tle_line1", config.SATELLITE_TLE_LINE1),
                tle_line2=form_data.get("tle_line2", config.SATELLITE_TLE_LINE2),
                epoch="",
                mean_motion=0,
                eccentricity=0,
                inclination=0,
                ra_of_asc_node=0,
                arg_of_pericenter=0,
                mean_anomaly=0,
            )

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

            app.logger.info(
                f"Calculating passes for {tle_data.satellite_name} on {date}"
            )

            # Find passes
            passes_gs1 = satellite_service.find_passes(
                tle_data, gs1, start_time, end_time, min_el
            )
            passes_gs2 = satellite_service.find_passes(
                tle_data, gs2, start_time, end_time, min_el
            )
            common_windows = satellite_service.find_common_windows(
                passes_gs1, passes_gs2
            )

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

        except Exception as e:
            app.logger.error(f"Error in calculation: {e}")
            return render_template("error.html", error_message=str(e)), 500

    @app.route("/satellite_position")
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
            default_date=default_date,
            default_time=default_time,
        )

    @app.route("/calculate_position", methods=["POST"])
    def calculate_position():
        """Calculate and display the satellite position."""
        try:
            form_data = request.form

            tle_data = TLEData(
                norad_id="",
                satellite_name=form_data.get("tle_name", config.SATELLITE_NAME),
                tle_line1=form_data.get("tle_line1", config.SATELLITE_TLE_LINE1),
                tle_line2=form_data.get("tle_line2", config.SATELLITE_TLE_LINE2),
                epoch="",
                mean_motion=0,
                eccentricity=0,
                inclination=0,
                ra_of_asc_node=0,
                arg_of_pericenter=0,
                mean_anomaly=0,
            )

            date = form_data.get("date")
            time = form_data.get("time")
            datetime_obj = datetime.strptime(f"{date} {time}:00", "%Y-%m-%d %H:%M:%S")

            position_data = satellite_service.calculate_position(tle_data, datetime_obj)

            return render_template(
                "satellite_position/position_calculator.html",
                tle_name=tle_data.satellite_name,
                tle_line1=tle_data.tle_line1,
                tle_line2=tle_data.tle_line2,
                default_date=date,
                default_time=time,
                position_data=position_data,
            )

        except Exception as e:
            app.logger.error(f"Error calculating position: {e}")
            return render_template("error.html", error_message=str(e)), 500

    @app.route("/tle-viewer")
    def tle_viewer():
        """Render the TLE history viewer page."""
        return render_template("tle/tle_viewer.html", norad_id="25544", days_back=30)

    @app.route("/fetch_tle_data", methods=["POST"])
    def fetch_tle_data():
        """Fetch and display TLE data for a given NORAD ID."""
        try:
            form_data = request.form
            norad_id = form_data.get("norad_id", "25544")
            days_back = int(form_data.get("days_back", 30))

            app.logger.info(
                f"TLE data fetch requested for NORAD ID {norad_id}, {days_back} days back"
            )

            # Fetch data
            current_tle = satellite_service.get_current_tle(norad_id)
            tle_history = satellite_service.get_tle_history(norad_id, days_back)
            tle_age_info = satellite_service.get_tle_age_info(norad_id)

            app.logger.info("TLE data fetch completed successfully")

            return render_template(
                "tle/tle_viewer.html",
                norad_id=norad_id,
                days_back=days_back,
                current_tle=current_tle,
                tle_history=tle_history,
                tle_age_info=tle_age_info,
            )

        except Exception as e:
            app.logger.error(f"Error fetching TLE data: {e}")
            return render_template(
                "tle/tle_viewer.html",
                norad_id=norad_id,
                days_back=days_back,
                error=str(e),
            )

    @app.route("/import_tle/<norad_id>")
    def import_tle(norad_id):
        """Import TLE data and redirect to the pass calculator."""
        try:
            tle_data = satellite_service.get_current_tle(norad_id)
            tomorrow = datetime.now() + timedelta(days=1)
            default_date = tomorrow.strftime("%Y-%m-%d")

            return render_template(
                "satellite_passes/index.html",
                success=f"TLE data imported for {tle_data.satellite_name}",
                gs1_name=config.STATION1_NAME,
                gs1_lat=config.STATION1_LAT,
                gs1_lon=config.STATION1_LON,
                gs1_elev=config.STATION1_ELEV,
                gs2_name=config.STATION2_NAME,
                gs2_lat=config.STATION2_LAT,
                gs2_lon=config.STATION2_LON,
                gs2_elev=config.STATION2_ELEV,
                min_el=config.MIN_ELEVATION,
                default_date=default_date,
                tle_name=tle_data.satellite_name,
                tle_line1=tle_data.tle_line1,
                tle_line2=tle_data.tle_line2,
            )

        except Exception as e:
            return redirect(
                url_for(
                    "index", error=f"Failed to import TLE for NORAD ID {norad_id}: {e}"
                )
            )

    @app.route("/cache/info")
    def cache_info():
        """Display cache information."""
        cache_service = CacheService(config)
        cache_stats = cache_service.get_cache_info()
        return jsonify(cache_stats)

    @app.route("/cache/clear", methods=["POST"])
    def clear_cache():
        """Clear all cached data."""
        cache_service = CacheService(config)
        cache_service.clear()
        return jsonify({"status": "success", "message": "Cache cleared"})

    @app.route('/cache/cleanup', methods=['POST'])
    def cleanup_cache():
        """Clean up expired cache files."""
        cache_service = CacheService(config)
        stats = cache_service.cleanup_expired_cache()
        return jsonify({
            "status": "success", 
            "message": f"Cleanup completed: {stats['removed']} files removed, {stats['errors']} errors"
        })

    @app.route('/cache/health')
    def cache_health():
        """Check cache health and freshness."""
        cache_service = CacheService(config)
        info = cache_service.get_cache_info()
        
        # Add health indicators
        if info.get("enabled"):
            total_files = info.get("total_files", 0)
            expired_count = sum(stats.get("expired", 0) for stats in info.get("cache_types", {}).values())
            
            info["health"] = {
                "status": "healthy" if expired_count < total_files * 0.5 else "needs_cleanup",
                "expired_percentage": round((expired_count / total_files * 100) if total_files > 0 else 0, 1)
            }
        
        return jsonify(info)


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
