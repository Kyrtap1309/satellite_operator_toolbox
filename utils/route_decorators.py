import logging
from functools import wraps

from flask import current_app, flash, redirect, url_for


def handle_route_errors(redirect_endpoint: str):
    """Decorator for consistent error handling in routes."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ValueError as e:
                flash(str(e), "error")
                return redirect(url_for(redirect_endpoint))

        return wrapper

    return decorator


def handle_calculation_errors(redirect_endpoint: str, preserve_form_data: bool = False):
    """
    Decorator for calculation routes with optional form data preservation.
    Used for routes that need to preserve user input on errors.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ValueError as e:
                # Validation errors - preserve form data if requested
                flash(str(e), "error")
                if preserve_form_data:
                    # For position calculator, preserve form data
                    from flask import request

                    if redirect_endpoint == "satellite_position":
                        return _handle_position_error(e, request.form)
                return redirect(url_for(redirect_endpoint))
            except Exception as e:
                # Log unexpected errors
                current_app.logger.error(f"Calculation error in {func.__name__}: {e}")
                flash(f"Calculation failed: {e}", "error")
                return redirect(url_for(redirect_endpoint))

        return wrapper

    return decorator


def _handle_position_error(error, form_data):
    """Handle errors in position calculation while preserving form data."""
    from flask import render_template

    input_method = form_data.get("input_method", "norad")
    return render_template(
        "satellite_position/position_calculator.html",
        tle_name=form_data.get("tle_name", "") if input_method == "tle" else "",
        tle_line1=form_data.get("tle_line1", "") if input_method == "tle" else "",
        tle_line2=form_data.get("tle_line2", "") if input_method == "tle" else "",
        norad_id=form_data.get("norad_id", "") if input_method == "norad" else "",
        default_date=form_data.get("date", ""),
        default_time=form_data.get("time", ""),
    )


def log_route_access(log_level: int = logging.INFO):
    """Decorator to log route access for monitoring."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import request

            current_app.logger.log(
                log_level,
                f"Route accessed: {func.__name__} - {request.method} {request.path}",
            )
            return func(*args, **kwargs)

        return wrapper

    return decorator
