from typing import Any

from models.satellite import SatellitePass


class DataFormatter:
    """Data formatting utilities."""

    @staticmethod
    def format_passes_for_display(passes: list[SatellitePass]) -> list[dict[str, Any]]:
        """Format passes for web display."""
        formatted_passes = []
        for i, pass_info in enumerate(passes, 1):
            date = pass_info.rise_time_utc.split()[0]
            rise_time_hm = pass_info.rise_time_utc.split()[1][:-3]
            set_time_hm = pass_info.set_time_utc.split()[1][:-3]

            formatted_passes.append(
                {
                    "Nr": i,
                    "Date": date,
                    "Rise Time (UTC)": rise_time_hm,
                    "Set Time (UTC)": set_time_hm,
                    "Max Elevation": f"{pass_info.max_elevation_degrees:.1f}°",
                }
            )
        return formatted_passes

    @staticmethod
    def format_common_windows(
        common_windows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Format common windows for web display."""
        formatted_common = []
        for i, window in enumerate(common_windows, 1):
            rise_time = window["rise_time_utc"]
            set_time = window["set_time_utc"]
            max_el = window["max_elevation_degrees"]

            date = rise_time.split()[0]
            rise_time_hm = rise_time.split()[1][:-3]
            set_time_hm = set_time.split()[1][:-3]

            formatted_common.append(
                {
                    "Nr": i,
                    "Date": date,
                    "Start (UTC)": rise_time_hm,
                    "End (UTC)": set_time_hm,
                    "Max Elevation": f"{max_el:.1f}°",
                    "Duration": window["duration_str"],
                }
            )
        return formatted_common

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
        for pass_info in passes_gs1:
            timeline_data.append(
                {
                    "group": gs1_name,
                    "start": pass_info.rise_time_utc,
                    "end": pass_info.set_time_utc,
                    "content": f"Max El: {pass_info.max_elevation_degrees:.1f}°",
                    "type": "range",
                    "className": "gs1-pass",
                }
            )

        # Ground station 2 passes
        for pass_info in passes_gs2:
            timeline_data.append(
                {
                    "group": gs2_name,
                    "start": pass_info.rise_time_utc,
                    "end": pass_info.set_time_utc,
                    "content": f"Max El: {pass_info.max_elevation_degrees:.1f}°",
                    "type": "range",
                    "className": "gs2-pass",
                }
            )

        # Common windows
        for window in common_windows:
            timeline_data.append(
                {
                    "group": "Common",
                    "start": window["rise_time_utc"],
                    "end": window["set_time_utc"],
                    "content": f"Max El: {window['max_elevation_degrees']:.1f}° | {window['duration_str']}",
                    "type": "range",
                    "className": "common-window",
                }
            )

        return timeline_data
