from skyfield.api import Topos, load, EarthSatellite, utc
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
import pandas as pd
import json

app = Flask(__name__)

# Default values
NAME = "Bluebon"
LINE1 = "1 62688U 25009CH  25124.74930353  .00015765  00000+0  69252-3 0  9994"
LINE2 = "2 62688  97.4284 205.7904 0001127  28.6595 331.4703 15.22003295 16668"

# Default ground station 1
GS1_NAME = "Sweden"
GS1_LAT = 65.337
GS1_LON = 21.425 
GS1_ELEVATION = 21

# Default ground station 2
GS2_NAME = "Poland"
GS2_LAT = 51.097  
GS2_LON = 17.069
GS2_ELEVATION = 116

MIN_ELEVATION = 3.0

def find_satellite_passes(tle_line1, tle_line2, tle_line0, station_lat, station_lon, station_elev, start_time_str, end_time_str, min_el):
    ts = load.timescale()
    satellite = EarthSatellite(tle_line1, tle_line2, tle_line0, ts)
    ground_station = Topos(latitude_degrees=station_lat, longitude_degrees=station_lon, elevation_m=station_elev)
    
    start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=utc)
    end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=utc)
    
    t0 = ts.from_datetime(start_dt)
    t1 = ts.from_datetime(end_dt)
    
    times, events = satellite.find_events(ground_station, t0, t1, altitude_degrees=min_el)
    
    passes = []
    for i in range(0, len(events) - 2, 3):
        if events[i] == 0 and events[i+1] == 1 and events[i+2] == 2:
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

def find_common_visibility_windows(passes_station1, passes_station2):
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
    
    common_windows.sort(key=lambda x: x['rise_time_utc'])
    return common_windows

def format_passes_for_display(passes):
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

@app.route('/')
def index():
    # Get tomorrow's date as default
    tomorrow = datetime.now() + timedelta(days=1)
    default_date = tomorrow.strftime('%Y-%m-%d')
    
    return render_template('index.html', 
                          gs1_name=GS1_NAME,
                          gs1_lat=GS1_LAT,
                          gs1_lon=GS1_LON,
                          gs1_elev=GS1_ELEVATION,
                          gs2_name=GS2_NAME,
                          gs2_lat=GS2_LAT,
                          gs2_lon=GS2_LON,
                          gs2_elev=GS2_ELEVATION,
                          min_el=MIN_ELEVATION,
                          default_date=default_date,
                          tle_name=NAME,
                          tle_line1=LINE1,
                          tle_line2=LINE2)

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.form
    
    # Get form data
    tle_name = data.get('tle_name', NAME)
    tle_line1 = data.get('tle_line1', LINE1)
    tle_line2 = data.get('tle_line2', LINE2)
    
    # Get ground station names
    gs1_name = data.get('gs1_name', GS1_NAME)
    gs2_name = data.get('gs2_name', GS2_NAME)
    
    # Get ground station coordinates
    gs1_lat = float(data.get('gs1_lat', GS1_LAT))
    gs1_lon = float(data.get('gs1_lon', GS1_LON))
    gs1_elev = float(data.get('gs1_elev', GS1_ELEVATION))
    
    gs2_lat = float(data.get('gs2_lat', GS2_LAT))
    gs2_lon = float(data.get('gs2_lon', GS2_LON))
    gs2_elev = float(data.get('gs2_elev', GS2_ELEVATION))
    
    min_el = float(data.get('min_el', MIN_ELEVATION))
    
    date = data.get('date')
    start_time = f"{date} 00:00:00"
    end_time = f"{date} 23:59:59"
    
    # Calculate passes
    passes_gs1 = find_satellite_passes(tle_line1, tle_line2, tle_name, 
                                       gs1_lat, gs1_lon, gs1_elev, 
                                       start_time, end_time, min_el)
    
    passes_gs2 = find_satellite_passes(tle_line1, tle_line2, tle_name, 
                                       gs2_lat, gs2_lon, gs2_elev, 
                                       start_time, end_time, min_el)
    
    common_windows = find_common_visibility_windows(passes_gs1, passes_gs2)
    
    # Format data for display
    formatted_gs1 = format_passes_for_display(passes_gs1)
    formatted_gs2 = format_passes_for_display(passes_gs2)
    
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
    
    # Prepare timeline data for visualization
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

if __name__ == '__main__':
    app.run(debug=True)