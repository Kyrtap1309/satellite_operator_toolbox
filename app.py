from skyfield.api import Topos, load, EarthSatellite, utc
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
import pandas as pd
import json

from typing import Any

app = Flask(__name__)


class Config:
    SATELLITE_NAME = "Bluebon"
    SATELLITE_TLE_LINE1 = "1 62688U 25009CH  25124.74930353  .00015765  00000+0  69252-3 0  9994"
    SATELLITE_TLE_LINE2 = "2 62688  97.4284 205.7904 0001127  28.6595 331.4703 15.22003295 16668"

    STATION1_NAME = "Sweden"
    STATION1_LAT = 65.337
    STATION1_LON = 21.425 
    STATION1_ELEV = 21
    
    STATION2_NAME = "Poland"
    STATION2_LAT = 51.097  
    STATION2_LON = 17.069
    STATION2_ELEV = 116
    
    MIN_ELEVATION = 3.0

app = Flask(__name__)

class SatelliteTracker:
    @staticmethod
    def find_passes(tle_line1: str, tle_line2: str, tle_name: str,
                    station_lat: float, station_lon: float, station_elev: float,
                    start_time_str: str, end_time_str: str, min_el: float) -> list[dict[str, Any]]:
        ts = load.timescale()
        satellite = EarthSatellite(tle_line1, tle_line2, tle_name, ts)
        ground_station = Topos(latitude_degrees=station_lat, longitude_degrees=station_lon, elevation_m=station_elev)

        start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=utc)
        end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=utc)

        t0 = ts.from_datetime(start_dt)
        t1 = ts.from_datetime(end_dt)

        times, events = satellite.find_events(ground_station, t0, t1, altitude_degrees=min_el)

        passes = []
        for i in range(0, len(events) -2, 3):
            if events[i] == 0 and events[i+1] == 1 and events[i+2] ==2:
                rise_time = times[i]
                culminate_time = times[i+1]
                set_time = times[i+2]

                difference = satellite - ground_station
                topocentric = difference.at(culminate_time)
                alt, az, distance = topocentric.altaz()
                max_elevation = alt.degrees
    
                passes.append({
                    "rise_time_utc": rise_time.utc_strftime('%Y-%m-%d %H:%M:%S'),
                    "culmination_time_utc": culminate_time.utc_strftime('%Y-%m-%d %H:%M:%S'),
                    "set_time_utc": set_time.utc_strftime('%Y-%m-%d %H:%M:%S'),
                    "max_elevation_degrees": round(max_elevation, 2)
                })

        return passes

    @staticmethod
    def find_common_windows(passes_station1: list[dict[str, Any]], 
                           passes_station2: list[dict[str, Any]]) -> list[dict[str, Any]]:
        common_windows = []
        
        for pass1 in passes_station1:
            rise_time1 = datetime.strptime(pass1['rise_time_utc'], '%Y-%m-%d %H:%M:%S')
            set_time1 = datetime.strptime(pass1['set_time_utc'], '%Y-%m-%d %H:%M:%S')
            
            for pass2 in passes_station2:
                rise_time2 = datetime.strptime(pass2['rise_time_utc'], '%Y-%m-%d %H:%M:%S')
                set_time2 = datetime.strptime(pass2['set_time_utc'], '%Y-%m-%d %H:%M:%S')
                
                if rise_time1 <= set_time2 and rise_time2 <= set_time1:
                    common_rise = max(rise_time1, rise_time2)
                    common_set = min(set_time1, set_time2)
                    
                    min_elevation = min(pass1['max_elevation_degrees'], pass2['max_elevation_degrees'])
                    
                    duration_sec = (common_set - common_rise).total_seconds()
                    duration_min = int(duration_sec // 60)
                    duration_sec_remainder = int(duration_sec % 60)
                    duration_str = f"{duration_min}m {duration_sec_remainder}s"
                    
                    common_window = {
                        'rise_time_utc': common_rise.strftime('%Y-%m-%d %H:%M:%S'),
                        'set_time_utc': common_set.strftime('%Y-%m-%d %H:%M:%S'),
                        'max_elevation_degrees': min_elevation,
                        'duration_seconds': duration_sec,
                        'duration_str': duration_str,
                        'station1_rise': pass1['rise_time_utc'],
                        'station1_set': pass1['set_time_utc'],
                        'station1_max_el': pass1['max_elevation_degrees'],
                        'station2_rise': pass2['rise_time_utc'],
                        'station2_set': pass2['set_time_utc'],
                        'station2_max_el': pass2['max_elevation_degrees']
                    }
                    
                    common_windows.append(common_window)
        
        return sorted(common_windows, key=lambda x: x['rise_time_utc'])
    
    @staticmethod
    def calculate_position(tle_line1: str, tle_line2: str, tle_name: str, time_str: str) -> dict[str, Any]:
        ts = load.timescale()
        satellite = EarthSatellite(tle_line1, tle_line2, tle_name, ts)

        time_dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=utc)
        t = ts.from_datetime(time_dt)

        geocentric = satellite.at(t)

        subpoint = geocentric.subpoint()

        return {
            'time_utc': time_str,
            'latitude': round(subpoint.latitude.degrees, 6),
            'longitude': round(subpoint.longitude.degrees, 6),
            'elevation': round(subpoint.elevation.m, 2),  # height in meters
            'satellite_name': tle_name
        }

class DataFormatter:
    @staticmethod
    def format_passes_for_display(passes: list[dict[str, Any]]) -> list[dict[str, any]]:
        formatted_passes = []
        for i, pass_info in enumerate(passes, 1):
            rise_time = pass_info['rise_time_utc']
            set_time = pass_info['set_time_utc']
            max_el = pass_info['max_elevation_degrees']
            date = rise_time.split()[0]
            rise_time_hm = rise_time.split()[1][:-3]
            set_time_hm = set_time.split()[1][:-3]

            formatted_passes.append({
                'Nr': i,
                'Date': date,
                'Rise Time (UTC)': rise_time_hm,
                'Set Time (UTC)': set_time_hm,
                'Max Elevation': f"{max_el:.1f}°"
            })
        return formatted_passes
    
    @staticmethod
    def format_common_windows(common_windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        formatted_common = []
        for i, window in enumerate(common_windows, 1):
            rise_time = window['rise_time_utc']
            set_time = window['set_time_utc']
            max_el = window['max_elevation_degrees']
            
            date = rise_time.split()[0]
            rise_time_hm = rise_time.split()[1][:-3]
            set_time_hm = set_time.split()[1][:-3]
            
            formatted_common.append({
                'Nr': i,
                'Date': date,
                'Start (UTC)': rise_time_hm,
                'End (UTC)': set_time_hm,
                'Max Elevation': f"{max_el:.1f}°",
                'Duration': window['duration_str']
            })
        return formatted_common
    
    @staticmethod
    def prepare_timeline_data(passes_gs1: list[dict[str, Any]], passes_gs2: list[dict[str, Any]], 
                              common_windows: list[dict[str, Any]], gs1_name: str, gs2_name: str) -> list[dict[str, Any]]:
        timeline_data = []
        for pass_info in passes_gs1:
            timeline_data.append({
                'group': gs1_name,
                'start': pass_info['rise_time_utc'],
                'end': pass_info['set_time_utc'],
                'content': f"Max El: {pass_info['max_elevation_degrees']:.1f}°",
                'type': 'range',
                'className': 'gs1-pass'
            })
        
        for pass_info in passes_gs2:
            timeline_data.append({
                'group': gs2_name,
                'start': pass_info['rise_time_utc'],
                'end': pass_info['set_time_utc'],
                'content': f"Max El: {pass_info['max_elevation_degrees']:.1f}°",
                'type': 'range',
                'className': 'gs2-pass'
            })
        
        for window in common_windows:
            timeline_data.append({
                'group': 'Common',
                'start': window['rise_time_utc'],
                'end': window['set_time_utc'],
                'content': f"Max El: {window['max_elevation_degrees']:.1f}° | {window['duration_str']}",
                'type': 'range',
                'className': 'common-window'
            })
        
        return timeline_data
    


@app.route('/')
def index():
    tomorrow = datetime.now() + timedelta(days=1)
    default_date = tomorrow.strftime('%Y-%m-%d')

    return render_template('index.html', 
                          gs1_name=Config.STATION1_NAME,
                          gs1_lat=Config.STATION1_LAT,
                          gs1_lon=Config.STATION1_LON,
                          gs1_elev=Config.STATION1_ELEV,
                          gs2_name=Config.STATION2_NAME,
                          gs2_lat=Config.STATION2_LAT,
                          gs2_lon=Config.STATION2_LON,
                          gs2_elev=Config.STATION2_ELEV,
                          min_el=Config.MIN_ELEVATION,
                          default_date=default_date,
                          tle_name=Config.SATELLITE_NAME,
                          tle_line1=Config.SATELLITE_TLE_LINE1,
                          tle_line2=Config.SATELLITE_TLE_LINE2)


@app.route('/calculate', methods=['POST'])
def calculate():
    form_data = request.form

    tle_name = form_data.get('tle_name', Config.SATELLITE_NAME)
    tle_line1 = form_data.get('tle_line1', Config.SATELLITE_TLE_LINE1)
    tle_line2 = form_data.get('tle_line2', Config.SATELLITE_TLE_LINE2)

    gs1_name = form_data.get('gs1_name', Config.STATION1_NAME)
    gs2_name = form_data.get('gs2_name', Config.STATION2_NAME)

    gs1_lat = float(form_data.get('gs1_lat', Config.STATION1_LAT))
    gs1_lon = float(form_data.get('gs1_lon', Config.STATION1_LON))
    gs1_elev = float(form_data.get('gs1_elev', Config.STATION1_ELEV))

    gs2_lat = float(form_data.get('gs2_lat', Config.STATION2_LAT))
    gs2_lon = float(form_data.get('gs2_lon', Config.STATION2_LON))
    gs2_elev = float(form_data.get('gs2_elev', Config.STATION2_ELEV))

    min_el = float(form_data.get('min_el', Config.MIN_ELEVATION))

    date = form_data.get('date')
    start_time = f"{date} 00:00:00"
    end_time = f"{date} 23:59:59"

    tracker = SatelliteTracker()
    passes_gs1 = tracker.find_passes(tle_line1, tle_line2, tle_name, 
                                    gs1_lat, gs1_lon, gs1_elev, 
                                    start_time, end_time, min_el)
    
    passes_gs2 = tracker.find_passes(tle_line1, tle_line2, tle_name, 
                                    gs2_lat, gs2_lon, gs2_elev, 
                                    start_time, end_time, min_el)
    
    common_windows = tracker.find_common_windows(passes_gs1, passes_gs2)

    formatter = DataFormatter()
    formatted_gs1 = formatter.format_passes_for_display(passes_gs1)
    formatted_gs2 = formatter.format_passes_for_display(passes_gs2)
    formatted_common = formatter.format_common_windows(common_windows)

    timeline_data = formatter.prepare_timeline_data(
        passes_gs1, passes_gs2, common_windows, gs1_name, gs2_name)
    
    return render_template('results.html',
                          gs1_name=gs1_name,
                          gs2_name=gs2_name,
                          gs1_passes=formatted_gs1,
                          gs2_passes=formatted_gs2,
                          common_windows=formatted_common,
                          timeline_data=json.dumps(timeline_data),
                          date=date,
                          gs1_lat=gs1_lat,
                          gs1_lon=gs1_lon,
                          gs1_elev=gs1_elev,
                          gs2_lat=gs2_lat,
                          gs2_lon=gs2_lon,
                          gs2_elev=gs2_elev)


@app.route('/position')
def position():
    """Render the satellite position calculator page."""
    now = datetime.now()
    default_date = now.strftime('%Y-%m-%d')
    default_time = now.strftime('%H:%M:%S')

    default_time_hm = default_time.rsplit(':', 1)[0]

    return render_template('position_calculator.html',
                           tle_name=Config.SATELLITE_NAME,
                           tle_line1=Config.SATELLITE_TLE_LINE1,
                           tle_line2=Config.SATELLITE_TLE_LINE2,
                           default_date=default_date,
                           default_time=default_time_hm)


@app.route('/calculate_position', methods=['POST'])
def calculate_position():
    """Calculate and display the satellite position."""

    form_data = request.form

    tle_name = form_data.get('tle_name', Config.SATELLITE_NAME)
    tle_line1 = form_data.get('tle_line1', Config.SATELLITE_TLE_LINE1)
    tle_line2 = form_data.get('tle_line2', Config.SATELLITE_TLE_LINE2)

    date = form_data.get('date')
    time = form_data.get('time')

    datetime_str = f"{date} {time}:00"

    tracker = SatelliteTracker()
    position_data = tracker.calculate_position(tle_line1, tle_line2, tle_name, datetime_str)

    return render_template('position_calculator.html',
                           tle_name=tle_name,
                           tle_line1=tle_line1,
                           tle_line2=tle_line2,
                           default_date=date,
                           default_time=time,
                           position_data=position_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)