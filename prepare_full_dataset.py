"""
Prepare Full Dataset for Training
Loads PurpleAir data, fetches historical wind direction from Meteostat,
and prepares the complete dataset with all features before training
"""

import pandas as pd
import numpy as np
import os
import sys
import json
from datetime import datetime
from meteostat import stations, hourly, Point
from geopy.distance import geodesic
import warnings
warnings.filterwarnings('ignore')

# Import from the pipeline (we'll copy these functions or adapt them)
# For now, let's create a standalone version that works with the full dataset


def load_purpleair_data(data_directory):
    """
    Load all PurpleAir sensor CSV files from the full dataset directory.
    
    Args:
        data_directory: Path to directory containing sensor CSV files
        
    Returns:
        DataFrame with columns: sensor_id, time_stamp, humidity, temperature, pm2_5_atm
    """
    import glob
    
    csv_files = glob.glob(os.path.join(data_directory, "*30-Minute Average.csv"))
    
    if not csv_files:
        raise ValueError(f"No CSV files found in {data_directory}")
    
    all_data = []
    
    for file_path in csv_files:
        # Extract sensor ID from filename (first number before space)
        filename = os.path.basename(file_path)
        sensor_id = filename.split()[0]
        
        try:
            df = pd.read_csv(file_path)
            df['sensor_id'] = int(sensor_id)
            # Parse timestamps and ensure they're timezone-aware (convert to UTC)
            df['time_stamp'] = pd.to_datetime(df['time_stamp'], utc=True)
            
            # Standardize column names
            df.columns = df.columns.str.replace('pm2.5_atm', 'pm2_5_atm')
            
            all_data.append(df)
            print(f"Loaded {len(df)} rows from sensor {sensor_id}")
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            continue
    
    if not all_data:
        raise ValueError("No data was successfully loaded")
    
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Sort by sensor_id and time_stamp
    combined_df = combined_df.sort_values(['sensor_id', 'time_stamp']).reset_index(drop=True)
    
    print(f"\nTotal combined rows: {len(combined_df)}")
    print(f"Number of sensors: {combined_df['sensor_id'].nunique()}")
    print(f"Date range: {combined_df['time_stamp'].min()} to {combined_df['time_stamp'].max()}")
    
    return combined_df


def load_station_coverage_cache(cache_file='station_coverage_cache.json'):
    """Load station coverage cache from JSON file."""
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load cache file {cache_file}: {e}")
    return {}


def save_station_coverage_cache(cache, cache_file='station_coverage_cache.json'):
    """Save station coverage cache to JSON file."""
    try:
        with open(cache_file, 'w') as f:
            json.dump(cache, f, indent=2, default=str)
    except Exception as e:
        print(f"Warning: Could not save cache file {cache_file}: {e}")


def test_station_wdir_coverage(station_id, test_start, test_end, cache=None):
    """
    Test wind direction coverage for a station using a sample window.
    
    Args:
        station_id: Station ID (string)
        test_start: Start date for test window (datetime)
        test_end: End date for test window (datetime)
        cache: Cache dictionary to check/save results
        
    Returns:
        float: Coverage percentage (0-100), or None if error
    """
    # Check cache first
    cache_key = f"{station_id}_{test_start.strftime('%Y%m%d')}_{test_end.strftime('%Y%m%d')}"
    if cache is not None and cache_key in cache:
        print(f"    Using cached coverage for station {station_id}: {cache[cache_key]:.1f}%")
        return cache[cache_key]
    
    try:
        # Fetch sample data - Hourly takes station ID as string
        sample_data = hourly(station_id, start=test_start, end=test_end)
        data = sample_data.fetch()
        
        if data is None or data.empty:
            coverage = 0.0
        else:
            # Calculate coverage for wdir
            if 'wdir' in data.columns:
                wdir_notna = data['wdir'].notna().sum()
                total_rows = len(data)
                coverage = (wdir_notna / total_rows * 100) if total_rows > 0 else 0.0
            else:
                coverage = 0.0
        
        # Save to cache
        if cache is not None:
            cache[cache_key] = coverage
        
        return coverage
    except Exception as e:
        print(f"    Error testing station {station_id}: {e}")
        return None


def select_best_station(latitude, longitude, start_date, end_date, 
                        max_distance_km=50, min_coverage=50, preferred_coverage=80,
                        cache_file='station_coverage_cache.json'):
    """
    Select the best weather station for wind direction data.
    
    Args:
        latitude: Target latitude
        longitude: Target longitude
        start_date: Start date for full data range
        end_date: End date for full data range
        max_distance_km: Maximum distance in km (50 km first pass, 100 km second)
        min_coverage: Minimum acceptable coverage % (default 50)
        preferred_coverage: Preferred coverage % (default 80)
        cache_file: Path to cache file
        
    Returns:
        tuple: (selected_station, distance_km, coverage_pct) or (None, None, None) if none found
    """
    print(f"\nSelecting best weather station for wind direction...")
    print(f"Target location: ({latitude}, {longitude})")
    print(f"Full date range: {start_date} to {end_date}")
    print(f"Distance cap: {max_distance_km} km")
    print(f"Coverage thresholds: ≥{preferred_coverage}% preferred, ≥{min_coverage}% minimum")
    
    # Load cache
    cache = load_station_coverage_cache(cache_file)
    
    # Test window for coverage testing (June 1-7, 2025)
    test_start = datetime(2025, 6, 1)
    test_end = datetime(2025, 6, 7, 23, 59)
    
    print(f"\nTesting stations using sample window: {test_start.date()} to {test_end.date()}")
    
    # Find nearby stations
    point = Point(latitude, longitude)
    
    # Fetch top 20 stations (more than we need, but ensures we have options)
    try:
        station_list = stations.nearby(point, radius=max_distance_km*1000, limit=20)  # radius in meters
    except Exception as e:
        print(f"Error fetching stations: {e}")
        return None, None, None
    
    if station_list is None or len(station_list) == 0:
        print("No stations found nearby")
        return None, None, None
    
    print(f"Found {len(station_list)} nearby stations")
    
    # Test each station for coverage
    station_results = []
    target_point = (latitude, longitude)
    
    for station_id, station_row in station_list.iterrows():
        # Distance is already in the dataframe (in meters), convert to km
        distance_m = station_row.get('distance', None)
        if distance_m is None:
            # Calculate manually if not provided
            station_point = (station_row['latitude'], station_row['longitude'])
            distance_km = geodesic(target_point, station_point).kilometers
        else:
            distance_km = distance_m / 1000.0  # Convert meters to km
        
        if distance_km > max_distance_km:
            continue  # Skip stations beyond distance cap
        
        station_name = station_row.get('name', 'Unknown')
        print(f"\n  Testing station {station_id} ({station_name}):")
        print(f"    Distance: {distance_km:.2f} km")
        
        # Test coverage
        coverage = test_station_wdir_coverage(station_id, test_start, test_end, cache)
        
        if coverage is not None:
            print(f"    Coverage: {coverage:.1f}%")
            station_results.append({
                'station_id': station_id,
                'station_row': station_row,
                'distance_km': distance_km,
                'coverage_pct': coverage
            })
        else:
            print(f"    Coverage: Failed to test")
    
    # Save cache
    save_station_coverage_cache(cache, cache_file)
    
    if not station_results:
        print(f"\nNo stations found within {max_distance_km} km with valid coverage data")
        return None, None, None
    
    # Sort by coverage (descending), then by distance (ascending)
    station_results.sort(key=lambda x: (-x['coverage_pct'], x['distance_km']))
    
    # Find best station meeting criteria
    best_station_id = None
    best_station_row = None
    best_distance = None
    best_coverage = None
    
    # First, try to find one with preferred coverage
    for result in station_results:
        if result['coverage_pct'] >= preferred_coverage:
            best_station_id = result['station_id']
            best_station_row = result['station_row']
            best_distance = result['distance_km']
            best_coverage = result['coverage_pct']
            print(f"\n✓ Found station with preferred coverage (≥{preferred_coverage}%):")
            break
    
    # If none found, use best available if it meets minimum
    if best_station_id is None and station_results:
        best_result = station_results[0]
        if best_result['coverage_pct'] >= min_coverage:
            best_station_id = best_result['station_id']
            best_station_row = best_result['station_row']
            best_distance = best_result['distance_km']
            best_coverage = best_result['coverage_pct']
            print(f"\n✓ Using best available station (coverage ≥{min_coverage}%):")
        else:
            print(f"\n✗ No station meets minimum coverage threshold ({min_coverage}%)")
            print(f"  Best available: {best_result['coverage_pct']:.1f}% at {best_result['distance_km']:.2f} km")
            return None, None, None
    
    if best_station_id is not None:
        print(f"  Station ID: {best_station_id}")
        print(f"  Station Name: {best_station_row.get('name', 'Unknown')}")
        print(f"  Distance: {best_distance:.2f} km")
        print(f"  Test Coverage: {best_coverage:.1f}%")
    
    # Create a dict-like object for compatibility
    best_station = {
        'id': best_station_id,
        'name': best_station_row.get('name', 'Unknown'),
        'latitude': best_station_row['latitude'],
        'longitude': best_station_row['longitude']
    }
    
    return best_station, best_distance, best_coverage


def fetch_historical_wind_direction(latitude, longitude, start_date, end_date):
    """
    Fetch historical hourly wind direction from Meteostat using station-based approach.
    
    Args:
        latitude: Latitude of location (Fremont, CA center)
        longitude: Longitude of location (Fremont, CA center)
        start_date: Start date (datetime or string) - should match dataset start
        end_date: End date (datetime or string) - should match dataset end
        
    Returns:
        tuple: (wind_df DataFrame, station_info dict) or (None, None) if no valid station found
        wind_df has columns: timestamp_hour (timezone-naive America/Los_Angeles), wdir
    """
    # Convert dates to datetime if strings
    if isinstance(start_date, str):
        start_date = pd.to_datetime(start_date)
    if isinstance(end_date, str):
        end_date = pd.to_datetime(end_date)
    
    # Convert to timezone-naive local time (America/Los_Angeles)
    # If timezone-aware, convert to America/Los_Angeles first, then remove timezone
    tz_local = 'America/Los_Angeles'
    
    if isinstance(start_date, pd.Timestamp):
        if start_date.tz is not None:
            start_date = start_date.tz_convert(tz_local).tz_localize(None)
        else:
            # Assume UTC if naive, convert to local
            start_date = start_date.tz_localize('UTC').tz_convert(tz_local).tz_localize(None)
    
    if isinstance(end_date, pd.Timestamp):
        if end_date.tz is not None:
            end_date = end_date.tz_convert(tz_local).tz_localize(None)
        else:
            end_date = end_date.tz_localize('UTC').tz_convert(tz_local).tz_localize(None)
    
    # Convert to Python datetime if needed
    if isinstance(start_date, pd.Timestamp):
        start_date = start_date.to_pydatetime()
    if isinstance(end_date, pd.Timestamp):
        end_date = end_date.to_pydatetime()
    
    print(f"\n{'='*80}")
    print(f"FETCHING HISTORICAL WIND DIRECTION FROM METEOSTAT")
    print(f"{'='*80}")
    print(f"Target location: ({latitude}, {longitude})")
    print(f"Date range: {start_date} to {end_date}")
    print(f"Timezone: {tz_local} (timezone-naive)")
    
    # Step 1: Try 50 km radius first
    station, distance, test_coverage = select_best_station(
        latitude, longitude, start_date, end_date,
        max_distance_km=50, min_coverage=50, preferred_coverage=80
    )
    
    # Step 2: If no station found, try 100 km radius
    if station is None:
        print(f"\nNo suitable station found within 50 km. Expanding search to 100 km...")
        station, distance, test_coverage = select_best_station(
            latitude, longitude, start_date, end_date,
            max_distance_km=100, min_coverage=50, preferred_coverage=80
        )
    
    if station is None:
        print(f"\n✗ No suitable weather station found. Skipping wind direction features.")
        print(f"  Training will continue without wind direction data.")
        return None, None
    
    # Step 3: Fetch full data from selected station
    print(f"\n{'='*80}")
    print(f"FETCHING FULL WIND DATA FROM SELECTED STATION")
    print(f"{'='*80}")
    print(f"Station ID: {station['id']}")
    print(f"Station Name: {station.get('name', 'Unknown')}")
    print(f"Distance: {distance:.2f} km")
    print(f"Full date range: {start_date} to {end_date}")
    
    try:
        # Hourly takes station ID as string
        timeseries = hourly(station['id'], start=start_date, end=end_date)
        data = timeseries.fetch()
        
        if data is None or data.empty:
            print(f"✗ Error: No data returned from station {station['id']}")
            return None, None
    except Exception as e:
        print(f"✗ Error fetching data from station {station['id']}: {e}")
        return None, None
    
    # Extract wdir column
    wind_df = pd.DataFrame({
        'timestamp_hour': data.index,
        'wdir': data['wdir'].values
    })
    
    # Convert timestamp to timezone-naive local time
    # Meteostat returns data in the station's timezone, convert to America/Los_Angeles
    if wind_df['timestamp_hour'].dtype == 'datetime64[ns]':
        # If already datetime, check if timezone-aware
        if hasattr(wind_df['timestamp_hour'].iloc[0], 'tz') and wind_df['timestamp_hour'].iloc[0].tz is not None:
            wind_df['timestamp_hour'] = pd.to_datetime(wind_df['timestamp_hour']).dt.tz_convert(tz_local).dt.tz_localize(None)
        else:
            # Assume UTC if naive, convert to local
            wind_df['timestamp_hour'] = pd.to_datetime(wind_df['timestamp_hour']).dt.tz_localize('UTC').dt.tz_convert(tz_local).dt.tz_localize(None)
    else:
        wind_df['timestamp_hour'] = pd.to_datetime(wind_df['timestamp_hour'], utc=True).dt.tz_convert(tz_local).dt.tz_localize(None)
    
    # Calculate actual coverage for full period
    initial_rows = len(wind_df)
    non_null_wdir = wind_df['wdir'].notna().sum()
    actual_coverage = (non_null_wdir / initial_rows * 100) if initial_rows > 0 else 0.0
    
    print(f"\n✓ Data fetched successfully")
    print(f"  Total hourly records: {len(wind_df)}")
    print(f"  Records with wind direction: {non_null_wdir} ({actual_coverage:.2f}%)")
    print(f"  Wind direction range: {wind_df['wdir'].min():.1f}° to {wind_df['wdir'].max():.1f}°")
    
    # Store station info for diagnostics
    station_info = {
        'station_id': station['id'],
        'station_name': station.get('name', 'Unknown'),
        'distance_km': distance,
        'test_coverage_pct': test_coverage,
        'actual_coverage_pct': actual_coverage,
        'latitude': station['latitude'],
        'longitude': station['longitude']
    }
    
    return wind_df, station_info


def merge_wind_direction(df, wind_df, station_info=None):
    """
    Merge historical wind direction into the PurpleAir dataframe.
    
    Args:
        df: PurpleAir DataFrame with time_stamp column (30-minute intervals)
        wind_df: Wind direction DataFrame with timestamp_hour and wdir (hourly, timezone-naive local)
        station_info: Dictionary with station information for diagnostics
        
    Returns:
        DataFrame with added wdir, wind_dir_x, wind_dir_y columns
    """
    df = df.copy()
    tz_local = 'America/Los_Angeles'
    
    print(f"\n{'='*80}")
    print(f"MERGING WIND DIRECTION DATA")
    print(f"{'='*80}")
    
    # Convert PurpleAir timestamps to timezone-naive local time (America/Los_Angeles)
    # Original data might be timezone-aware UTC, convert to local then make naive
    df['time_stamp'] = pd.to_datetime(df['time_stamp'], utc=True)  # Ensure UTC-aware
    df['time_stamp'] = df['time_stamp'].dt.tz_convert(tz_local).dt.tz_localize(None)  # Convert to local, then naive
    
    # Create hourly timestamp for merging (floor to hour)
    df['timestamp_hour'] = df['time_stamp'].dt.floor('H')
    
    # Ensure wind_df timestamp_hour is also timezone-naive local
    if wind_df is not None and len(wind_df) > 0:
        # wind_df should already be timezone-naive local from fetch function
        wind_df = wind_df.copy()
        wind_df['timestamp_hour'] = pd.to_datetime(wind_df['timestamp_hour'])
        
        # Double-check: if somehow timezone-aware, convert
        if hasattr(wind_df['timestamp_hour'].iloc[0], 'tz') and wind_df['timestamp_hour'].iloc[0].tz is not None:
            wind_df['timestamp_hour'] = wind_df['timestamp_hour'].dt.tz_convert(tz_local).dt.tz_localize(None)
        
        # Merge wind direction data using left join
        print(f"Merging wind direction data...")
        initial_rows = len(df)
        
        df = df.merge(wind_df[['timestamp_hour', 'wdir']], 
                      on='timestamp_hour', 
                      how='left')
        
        # Forward-fill missing wdir values with limit of 6 hours
        # This ensures rows at :30 inherit the value from :00 of the same hour
        # But limits propagation to max 6 hours to avoid stale data
        print(f"Forward-filling missing values (max 6 hours)...")
        df['wdir'] = df.groupby('sensor_id')['wdir'].ffill(limit=6)
        
        # Do NOT backward-fill or fill with 0 - leave NaNs as NaN
        
        # Calculate percentage of rows with non-null wdir
        non_null_count = df['wdir'].notna().sum()
        non_null_pct = (non_null_count / len(df)) * 100
        
        print(f"\n✓ Merge complete")
        print(f"  Initial rows: {initial_rows:,}")
        print(f"  Rows with wind direction: {non_null_count:,} / {len(df):,} ({non_null_pct:.2f}%)")
        
        # Print station diagnostics if available
        if station_info:
            print(f"\nSelected Station Information:")
            print(f"  Station ID: {station_info['station_id']}")
            print(f"  Station Name: {station_info['station_name']}")
            print(f"  Distance: {station_info['distance_km']:.2f} km")
            print(f"  Test Coverage (June 1-7): {station_info['test_coverage_pct']:.1f}%")
            print(f"  Actual Coverage (full period): {station_info['actual_coverage_pct']:.2f}%")
            print(f"  Station Location: ({station_info['latitude']:.4f}, {station_info['longitude']:.4f})")
        
        if non_null_pct < 50:
            print(f"\n⚠ Warning: Only {non_null_pct:.1f}% of rows have wind direction data")
            print(f"  Consider selecting a different station or expanding search radius.")
        elif non_null_pct < 80:
            print(f"\n⚠ Note: {non_null_pct:.1f}% coverage is below preferred threshold (80%)")
            print(f"  Model may still benefit from wind features, but coverage is limited.")
    else:
        # No wind data available
        print(f"No wind data to merge. Creating empty wind columns...")
        df['wdir'] = np.nan
        non_null_pct = 0.0
    
    # Convert wind direction to model-friendly features
    print(f"\nConverting wind direction to x, y components...")
    
    # Convert degrees to radians (only for non-null values)
    mask = df['wdir'].notna()
    df.loc[mask, 'wind_dir_x'] = np.cos(np.radians(df.loc[mask, 'wdir']))
    df.loc[mask, 'wind_dir_y'] = np.sin(np.radians(df.loc[mask, 'wdir']))
    
    # Set NaN for x and y where wdir was NaN
    df.loc[~mask, 'wind_dir_x'] = np.nan
    df.loc[~mask, 'wind_dir_y'] = np.nan
    
    print(f"✓ Created wind_dir_x and wind_dir_y columns")
    print(f"  Non-null wind_dir_x: {df['wind_dir_x'].notna().sum():,}")
    print(f"  Non-null wind_dir_y: {df['wind_dir_y'].notna().sum():,}")
    
    # Show sample of merged data (first 5 rows with wind direction)
    print(f"\n{'='*80}")
    print(f"SAMPLE OF MERGED DATA (first 5 rows with wind direction)")
    print(f"{'='*80}")
    sample_df = df[df['wdir'].notna()].head(5)
    if len(sample_df) > 0:
        sample_cols = ['sensor_id', 'time_stamp', 'pm2_5_atm', 'wdir', 'wind_dir_x', 'wind_dir_y']
        print(sample_df[sample_cols].to_string(index=False))
    else:
        print("No rows with wind direction data to display")
    
    # Summary statistics
    if df['wdir'].notna().sum() > 0:
        print(f"\nWind Direction Statistics:")
        print(f"  Min: {df['wdir'].min():.1f}°")
        print(f"  Max: {df['wdir'].max():.1f}°")
        print(f"  Mean: {df['wdir'].mean():.1f}°")
        print(f"  Std: {df['wdir'].std():.1f}°")
    
    return df


def load_sensor_locations(data_directory, location_file='sensor_locations.pkl'):
    """
    Load sensor location information if available.
    
    Args:
        data_directory: Path to directory (will check in both locations)
        location_file: Name of sensor locations file
        
    Returns:
        DataFrame with sensor locations or None
    """
    import pickle
    
    # Try current directory first
    location_path = os.path.join(data_directory, location_file)
    
    # Also try the 2-month data directory (where we saved it earlier)
    alt_location_path = os.path.join(
        os.path.expanduser("~/Downloads/PAIC Data 2 Months"),
        location_file
    )
    
    for path in [location_path, alt_location_path]:
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    locations_df = pickle.load(f)
                print(f"\nLoaded location data for {len(locations_df)} sensors from {path}")
                return locations_df
            except Exception as e:
                print(f"Error loading {path}: {e}")
                continue
    
    print(f"\nWarning: Sensor locations file not found. Spatial features will be limited.")
    return None


def prepare_full_dataset(data_directory, latitude=37.5483, longitude=-121.9886):
    """
    Main function to prepare the complete dataset with all features including wind direction.
    
    Args:
        data_directory: Path to directory containing sensor CSV files
        latitude: Latitude for Meteostat query (Fremont, CA center)
        longitude: Longitude for Meteostat query (Fremont, CA center)
        
    Returns:
        DataFrame ready for feature engineering and training
    """
    print("="*80)
    print("PREPARING FULL DATASET FOR TRAINING")
    print("="*80)
    
    # Step 1: Load PurpleAir data
    print("\nStep 1: Loading PurpleAir sensor data...")
    print("-"*80)
    df = load_purpleair_data(data_directory)
    
    # Step 2: Get date range from data (preserve original timezone)
    start_date = df['time_stamp'].min()
    end_date = df['time_stamp'].max()
    
    print(f"\nDataset date range: {start_date} to {end_date}")
    
    # Step 3: Fetch historical wind direction for EXACT date range
    print("\nStep 2: Fetching historical wind direction from Meteostat...")
    print("-"*80)
    wind_result = fetch_historical_wind_direction(latitude, longitude, start_date, end_date)
    
    # Handle return value (now returns tuple: (wind_df, station_info) or (None, None))
    if wind_result is None or wind_result[0] is None:
        wind_df = None
        station_info = None
        print("\n⚠ No wind data available - model will train without wind features.")
    else:
        wind_df, station_info = wind_result
    
    # Step 4: Merge wind direction into dataset
    print("\nStep 3: Merging wind direction with PurpleAir data...")
    print("-"*80)
    df = merge_wind_direction(df, wind_df, station_info)
    
    # Step 5: Add sensor locations if available
    print("\nStep 4: Adding sensor location data...")
    print("-"*80)
    locations_df = load_sensor_locations(data_directory)
    if locations_df is not None:
        df = df.merge(
            locations_df[['sensor_id', 'latitude', 'longitude', 'name']],
            on='sensor_id',
            how='left'
        )
        print(f"Added location data. Sensors with locations: {df['latitude'].notna().sum() / len(df) * 100:.1f}%")
    else:
        print("No location data found. Skipping spatial features.")
    
    # Step 6: Basic data cleaning
    print("\nStep 5: Cleaning data...")
    print("-"*80)
    initial_rows = len(df)
    
    # Remove invalid values
    df = df.dropna(subset=['pm2_5_atm', 'humidity', 'temperature', 'time_stamp'])
    df = df[(df['pm2_5_atm'] >= 0) & (df['pm2_5_atm'] <= 1000)]
    df = df[(df['humidity'] >= 0) & (df['humidity'] <= 100)]
    df = df[(df['temperature'] >= -10) & (df['temperature'] <= 120)]
    
    removed = initial_rows - len(df)
    if removed > 0:
        print(f"Removed {removed} rows with invalid data ({removed/initial_rows*100:.1f}%)")
    
    print(f"Final dataset: {len(df)} rows, {df['sensor_id'].nunique()} sensors")
    
    # Verification
    print("\n" + "="*80)
    print("DATASET PREPARATION COMPLETE")
    print("="*80)
    print(f"\nDataset shape: {df.shape}")
    print(f"Date range: {df['time_stamp'].min()} to {df['time_stamp'].max()}")
    print(f"\nColumns: {list(df.columns)}")
    print(f"\nWind direction coverage: {df['wdir'].notna().sum() / len(df) * 100:.2f}%")
    print(f"\nSample data:")
    print(df[['sensor_id', 'time_stamp', 'pm2_5_atm', 'humidity', 'temperature', 'wdir', 'wind_dir_x', 'wind_dir_y']].head(10).to_string(index=False))
    
    return df


if __name__ == "__main__":
    # Get data directory (current directory where script is run)
    data_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Prepare full dataset
    df_complete = prepare_full_dataset(data_dir, latitude=37.5483, longitude=-121.9886)
    
    # Save prepared dataset
    output_file = os.path.join(data_dir, 'purpleair_complete_with_wind.csv')
    print(f"\nSaving prepared dataset to: {output_file}")
    df_complete.to_csv(output_file, index=False)
    print(f"Saved {len(df_complete)} rows")
    print("\nDataset is ready for feature engineering and model training!")

