from datetime import datetime
from typing import Any

from models.satellite import SatellitePass


class DataFormatter:
    """Data formatting utilities."""

    @staticmethod
    def format_passes_for_display(passes: list[SatellitePass]) -> list[dict[str, Any]]:
        """Format satellite passes for display in tables."""
        formatted_passes = []
        for i, pass_info in enumerate(passes, 1):
            # Parse times to calculate duration
            rise_time = datetime.strptime(pass_info.rise_time_utc, "%Y-%m-%d %H:%M:%S")
            set_time = datetime.strptime(pass_info.set_time_utc, "%Y-%m-%d %H:%M:%S")
            duration_seconds = int((set_time - rise_time).total_seconds())

            formatted_passes.append(
                {
                    "Nr": i,
                    "Date": rise_time.strftime("%Y-%m-%d"),
                    "Rise Time (UTC)": rise_time.strftime("%H:%M:%S"),
                    "Set Time (UTC)": set_time.strftime("%H:%M:%S"),
                    "Max Elevation": f"{pass_info.max_elevation_degrees:.2f}°",
                    "Duration (s)": duration_seconds,
                }
            )
        return formatted_passes

    @staticmethod
    def format_common_windows_for_display(common_windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Format common visibility windows for display."""
        formatted_windows = []
        for i, window in enumerate(common_windows, 1):
            # Parse times
            start_time = datetime.strptime(window["rise_time_utc"], "%Y-%m-%d %H:%M:%S")
            end_time = datetime.strptime(window["set_time_utc"], "%Y-%m-%d %H:%M:%S")

            formatted_windows.append(
                {
                    "Nr": i,
                    "Date": start_time.strftime("%Y-%m-%d"),
                    "Start (UTC)": start_time.strftime("%H:%M:%S"),
                    "End (UTC)": end_time.strftime("%H:%M:%S"),
                    "Max Elevation": f"{window['max_elevation_degrees']:.2f}°",
                    "Duration": window["duration_str"],
                    "Duration (s)": window["duration_seconds"],
                }
            )
        return formatted_windows

    @staticmethod
    def prepare_timeline_data(
        passes_gs1: list[SatellitePass],
        passes_gs2: list[SatellitePass],
        common_windows: list[dict[str, Any]],
        gs1_name: str,
        gs2_name: str,
    ) -> list[dict[str, Any]]:
        """Prepare timeline data for visualization."""
        timeline_data = []

        # Ground station 1 passes
        timeline_data.extend(
            [
                {
                    "group": gs1_name,
                    "start": pass_info.rise_time_utc,
                    "end": pass_info.set_time_utc,
                    "content": f"Max El: {pass_info.max_elevation_degrees:.2f}°",
                    "type": "range",
                    "className": "gs1-pass",
                }
                for pass_info in passes_gs1
            ]
        )

        # Ground station 2 passes
        timeline_data.extend(
            [
                {
                    "group": gs2_name,
                    "start": pass_info.rise_time_utc,
                    "end": pass_info.set_time_utc,
                    "content": f"Max El: {pass_info.max_elevation_degrees:.2f}°",
                    "type": "range",
                    "className": "gs2-pass",
                }
                for pass_info in passes_gs2
            ]
        )

        # Common windows
        common_timeline = [
            {
                "group": "Common",
                "start": window["rise_time_utc"],
                "end": window["set_time_utc"],
                "content": f"Max El: {window['max_elevation_degrees']:.2f}° | {window['duration_str']}",
                "type": "range",
                "className": "common-window",
            }
            for window in common_windows
        ]
        timeline_data.extend(common_timeline)

        return timeline_data
