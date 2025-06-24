from typing import Any

from models.satellite import SatellitePass


class DataFormatter:
    """Data formatting utilities."""

    @staticmethod
    def format_passes_for_display(passes: list[SatellitePass]) -> list[dict[str, Any]]:
        """Format passes for web display."""
        return [
            {
                "Nr": i,
                "Date": pass_info.rise_time_utc.split()[0],
                "Rise Time (UTC)": pass_info.rise_time_utc.split()[1][:-3],
                "Set Time (UTC)": pass_info.set_time_utc.split()[1][:-3],
                "Max Elevation": f"{pass_info.max_elevation_degrees:.1f}°",
            }
            for i, pass_info in enumerate(passes, 1)
        ]

    @staticmethod
    def format_common_windows(
        common_windows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Format common windows for web display."""
        return [
            {
                "Nr": i,
                "Date": window["rise_time_utc"].split()[0],
                "Start (UTC)": window["rise_time_utc"].split()[1][:-3],
                "End (UTC)": window["set_time_utc"].split()[1][:-3],
                "Max Elevation": f"{window['max_elevation_degrees']:.1f}°",
                "Duration": window["duration_str"],
            }
            for i, window in enumerate(common_windows, 1)
        ]

    @staticmethod
    def prepare_timeline_data(
        passes_gs1: list[SatellitePass],
        passes_gs2: list[SatellitePass],
        common_windows: list[dict[str, Any]],
        gs1_name: str,
        gs2_name: str,
    ) -> list[dict[str, Any]]:
        """Prepare timeline data for visualization."""
        # Ground station 1 passes
        gs1_timeline = [
            {
                "group": gs1_name,
                "start": pass_info.rise_time_utc,
                "end": pass_info.set_time_utc,
                "content": f"Max El: {pass_info.max_elevation_degrees:.1f}°",
                "type": "range",
                "className": "gs1-pass",
            }
            for pass_info in passes_gs1
        ]

        # Ground station 2 passes
        gs2_timeline = [
            {
                "group": gs2_name,
                "start": pass_info.rise_time_utc,
                "end": pass_info.set_time_utc,
                "content": f"Max El: {pass_info.max_elevation_degrees:.1f}°",
                "type": "range",
                "className": "gs2-pass",
            }
            for pass_info in passes_gs2
        ]

        # Common windows
        common_timeline = [
            {
                "group": "Common",
                "start": window["rise_time_utc"],
                "end": window["set_time_utc"],
                "content": f"Max El: {window['max_elevation_degrees']:.1f}° | {window['duration_str']}",
                "type": "range",
                "className": "common-window",
            }
            for window in common_windows
        ]

        return gs1_timeline + gs2_timeline + common_timeline
