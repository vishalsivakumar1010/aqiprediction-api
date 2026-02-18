"""
Feature Engineering Module for Time Series Forecasting
Creates lagged features, rolling statistics, and time-based features
"""

import pandas as pd
import numpy as np
from datetime import datetime


def create_time_features(df, time_col='time_stamp'):
    """
    Extract time-based features from timestamp column.
    
    Args:
        df: DataFrame with time_stamp column
        time_col: Name of the timestamp column
        
    Returns:
        DataFrame with additional time features
    """
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    
    # Extract time components
    df['hour'] = df[time_col].dt.hour
    df['day_of_week'] = df[time_col].dt.dayofweek  # 0=Monday, 6=Sunday
    df['day_of_month'] = df[time_col].dt.day
    df['month'] = df[time_col].dt.month
    df['day_of_year'] = df[time_col].dt.dayofyear
    
    # Cyclical encoding for periodic features (sin/cos transformation)
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['day_of_week_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
    df['day_of_week_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
    df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
    df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
    
    return df


def create_lag_features(df, sensor_id_col='sensor_id', value_cols=['pm2_5_atm', 'humidity', 'temperature'], 
                        lags=[1, 2, 3, 4, 6, 12]):
    """
    Create lagged features for each sensor separately.
    
    Args:
        df: DataFrame sorted by sensor_id and time_stamp
        sensor_id_col: Column name for sensor ID
        value_cols: Columns to create lags for
        lags: List of lag periods (in 30-minute intervals)
              1 = 30 min, 2 = 1 hour, 6 = 3 hours, 12 = 6 hours
        
    Returns:
        DataFrame with lagged features
    """
    df = df.copy()
    df = df.sort_values([sensor_id_col, 'time_stamp']).reset_index(drop=True)
    
    # Group by sensor to create lags within each sensor's time series
    for sensor_id in df[sensor_id_col].unique():
        sensor_mask = df[sensor_id_col] == sensor_id
        sensor_data = df[sensor_mask].copy()
        
        for col in value_cols:
            for lag in lags:
                lag_col_name = f'{col}_lag_{lag}'
                df.loc[sensor_mask, lag_col_name] = sensor_data[col].shift(lag).values
        
        # Also create difference features (change from previous step)
        for col in value_cols:
            diff_col_name = f'{col}_diff'
            df.loc[sensor_mask, diff_col_name] = sensor_data[col].diff().values
    
    return df


def create_rolling_features(df, sensor_id_col='sensor_id', value_cols=['pm2_5_atm', 'humidity', 'temperature'],
                           windows=[2, 4, 6, 12, 24]):
    """
    Create rolling statistics for each sensor separately.
    
    Args:
        df: DataFrame sorted by sensor_id and time_stamp
        sensor_id_col: Column name for sensor ID
        value_cols: Columns to create rolling features for
        windows: List of window sizes (in 30-minute intervals)
                2 = 1 hour, 4 = 2 hours, 6 = 3 hours, 12 = 6 hours, 24 = 12 hours
        
    Returns:
        DataFrame with rolling features
    """
    df = df.copy()
    df = df.sort_values([sensor_id_col, 'time_stamp']).reset_index(drop=True)
    
    # Group by sensor to create rolling stats within each sensor's time series
    for sensor_id in df[sensor_id_col].unique():
        sensor_mask = df[sensor_id_col] == sensor_id
        sensor_data = df[sensor_mask].copy()
        
        for col in value_cols:
            for window in windows:
                # CRITICAL FIX: Rolling features must use ONLY past values (t-1, t-2, ...)
                # NOT including current value (t) to avoid data leakage in prediction
                # Shift by 1 so rolling at time t uses values at t-1, t-2, ..., t-window
                shifted_values = sensor_data[col].shift(1)
                
                # Rolling mean (using past values only)
                mean_col = f'{col}_rolling_mean_{window}'
                df.loc[sensor_mask, mean_col] = shifted_values.rolling(window=window, min_periods=1).mean().values
                
                # Rolling std (using past values only)
                std_col = f'{col}_rolling_std_{window}'
                df.loc[sensor_mask, std_col] = shifted_values.rolling(window=window, min_periods=1).std().values
                
                # Rolling min (using past values only)
                min_col = f'{col}_rolling_min_{window}'
                df.loc[sensor_mask, min_col] = shifted_values.rolling(window=window, min_periods=1).min().values
                
                # Rolling max (using past values only)
                max_col = f'{col}_rolling_max_{window}'
                df.loc[sensor_mask, max_col] = shifted_values.rolling(window=window, min_periods=1).max().values
    
    return df


def create_targets(df, sensor_id_col='sensor_id', target_col='pm2_5_atm', 
                   forecast_horizons=[2, 6]):
    """
    Create target variables for 1-hour (2 steps) and 3-hour (6 steps) ahead predictions.
    
    Args:
        df: DataFrame sorted by sensor_id and time_stamp
        sensor_id_col: Column name for sensor ID
        target_col: Column to create targets from
        forecast_horizons: List of forecast horizons in 30-minute intervals
                          2 = 1 hour, 6 = 3 hours
        
    Returns:
        DataFrame with target columns added
    """
    df = df.copy()
    df = df.sort_values([sensor_id_col, 'time_stamp']).reset_index(drop=True)
    
    for horizon in forecast_horizons:
        # PM2.5 target
        target_col_name = f'{target_col}_target_{horizon}h'
        aqi_target_col = f'aqi_target_{horizon}h'
        category_target_col = f'category_target_{horizon}h'
        
        # Group by sensor to shift within each sensor's time series
        for sensor_id in df[sensor_id_col].unique():
            sensor_mask = df[sensor_id_col] == sensor_id
            sensor_data = df[sensor_mask].copy()
            
            df.loc[sensor_mask, target_col_name] = sensor_data[target_col].shift(-horizon).values
        
        # Create AQI and category targets if AQI column exists
        if 'aqi' in df.columns:
            # Calculate AQI from PM2.5 target
            from aqi_utils import pm25_to_aqi, aqi_to_category
            
            df[aqi_target_col] = pm25_to_aqi(df[target_col_name])
            df[category_target_col] = aqi_to_category(df[aqi_target_col])
    
    return df


def create_spatial_features(df, sensor_id_col='sensor_id'):
    """
    Create spatial features from latitude and longitude.
    
    Args:
        df: DataFrame with latitude and longitude columns
        sensor_id_col: Column name for sensor ID
        
    Returns:
        DataFrame with additional spatial features
    """
    df = df.copy()
    
    if 'latitude' not in df.columns or 'longitude' not in df.columns:
        print("Warning: Latitude/longitude not found. Skipping spatial features.")
        return df
    
    # Calculate geographic center
    if df['latitude'].notna().any() and df['longitude'].notna().any():
        center_lat = df['latitude'].mean()
        center_lon = df['longitude'].mean()
        
        # Distance from center (Haversine formula approximation for small distances)
        # Using simplified formula for small areas (Fremont is ~5km across)
        df['distance_from_center_km'] = np.sqrt(
            ((df['latitude'] - center_lat) * 111) ** 2 +  # 1 degree lat ≈ 111 km
            ((df['longitude'] - center_lon) * 111 * np.cos(np.radians(center_lat))) ** 2
        )
        
        # Normalized coordinates (centered and scaled)
        lat_mean = df['latitude'].mean()
        lat_std = df['latitude'].std()
        lon_mean = df['longitude'].mean()
        lon_std = df['longitude'].std()
        
        if lat_std > 0:
            df['latitude_normalized'] = (df['latitude'] - lat_mean) / lat_std
        else:
            df['latitude_normalized'] = 0
        
        if lon_std > 0:
            df['longitude_normalized'] = (df['longitude'] - lon_mean) / lon_std
        else:
            df['longitude_normalized'] = 0
        
        # Coordinate features
        df['lat_lon_product'] = df['latitude'] * df['longitude']
        df['lat_squared'] = df['latitude'] ** 2
        df['lon_squared'] = df['longitude'] ** 2
        
        print(f"Created spatial features. Sensors have location data: {df['latitude'].notna().sum()}/{len(df)}")
    
    return df


def create_spatial_interaction_features(df, sensor_id_col='sensor_id'):
    """
    Create features based on spatial interactions between sensors.
    For each sensor, calculate average PM2.5 of nearby sensors at the same timestamp.
    This is computationally expensive, so we'll make it optional.
    
    Args:
        df: DataFrame with sensor_id, latitude, longitude, and pm2_5_atm
        sensor_id_col: Column name for sensor ID
        
    Returns:
        DataFrame with spatial interaction features
    """
    df = df.copy()
    
    if 'latitude' not in df.columns or 'longitude' not in df.columns:
        return df
    
    try:
        from scipy.spatial.distance import cdist
    except ImportError:
        print("Warning: scipy not available. Skipping spatial interaction features.")
        return df
    
    # Get unique sensors with locations
    sensor_locations = df[[sensor_id_col, 'latitude', 'longitude']].drop_duplicates(sensor_id_col).dropna()
    
    if len(sensor_locations) < 2:
        return df
    
    # Calculate pairwise distances between sensors (in km)
    coords = sensor_locations[['latitude', 'longitude']].values
    sensor_ids = sensor_locations[sensor_id_col].values
    
    # Convert lat/lon to approximate km (for small distances)
    center_lat = coords[:, 0].mean()
    coords_km = np.column_stack([
        (coords[:, 0] - center_lat) * 111,  # lat to km (1 degree ≈ 111 km)
        (coords[:, 1] - coords[:, 1].mean()) * 111 * np.cos(np.radians(center_lat))  # lon to km
    ])
    
    # Distance matrix in km
    distances = cdist(coords_km, coords_km)
    
    # For each sensor, find nearby sensors (within 5km)
    nearby_sensor_map = {}
    for idx, sensor_id in enumerate(sensor_ids):
        nearby_indices = np.where((distances[idx] < 5) & (distances[idx] > 0))[0]
        if len(nearby_indices) > 0:
            nearby_sensor_map[sensor_id] = sensor_ids[nearby_indices].tolist()
    
    # Initialize columns
    df['pm25_nearby_sensors_avg'] = np.nan
    df['pm25_nearby_sensors_std'] = np.nan
    
    # Calculate for each unique timestamp (more efficient than per-row)
    for time_stamp in df['time_stamp'].unique():
        time_mask = df['time_stamp'] == time_stamp
        time_data = df[time_mask].copy()
        
        # For each sensor in this timestamp
        for sensor_id in time_data[sensor_id_col].unique():
            sensor_mask = (df[sensor_id_col] == sensor_id) & time_mask
            
            if sensor_id in nearby_sensor_map:
                nearby_ids = nearby_sensor_map[sensor_id]
                nearby_pm25 = time_data[time_data[sensor_id_col].isin(nearby_ids)]['pm2_5_atm'].dropna().values
                
                if len(nearby_pm25) > 0:
                    df.loc[sensor_mask, 'pm25_nearby_sensors_avg'] = np.mean(nearby_pm25)
                    df.loc[sensor_mask, 'pm25_nearby_sensors_std'] = np.std(nearby_pm25) if len(nearby_pm25) > 1 else 0
    
    # Fill NaN values (no nearby sensors found) with the sensor's own PM2.5
    df['pm25_nearby_sensors_avg'] = df['pm25_nearby_sensors_avg'].fillna(df['pm2_5_atm'])
    df['pm25_nearby_sensors_std'] = df['pm25_nearby_sensors_std'].fillna(0)
    
    return df


def normalize_weather_schema(df):
    """
    Map inference column names to training schema so feature engineering matches.
    Training (05_feature_engineering) expects: temperature_2m, relative_humidity_2m,
    wind_speed_10m, wind_direction_10m, wdir, wind_dir_x, wind_dir_y.
    """
    df = df.copy()
    if 'humidity' in df.columns and 'relative_humidity_2m' not in df.columns:
        df['relative_humidity_2m'] = df['humidity']
    elif 'relative_humidity_2m' not in df.columns:
        df['relative_humidity_2m'] = np.nan
    if 'temperature' in df.columns and 'temperature_2m' not in df.columns:
        df['temperature_2m'] = df['temperature']
    elif 'temperature_2m' not in df.columns:
        df['temperature_2m'] = np.nan
    if 'wind_speed_10m' not in df.columns:
        df['wind_speed_10m'] = np.nan
    if 'wind_direction_10m' not in df.columns:
        df['wind_direction_10m'] = df['wdir'] if 'wdir' in df.columns else np.nan
    return df


def engineer_features(df, sensor_id_col='sensor_id', time_col='time_stamp',
                     include_targets=True, include_spatial_features=True):
    """
    Complete feature engineering pipeline.
    Matches training (05_feature_engineering) column names and transformations.
    
    Args:
        df: Raw sensor data DataFrame
        sensor_id_col: Column name for sensor ID
        time_col: Column name for timestamp
        include_targets: Whether to create target variables
        include_spatial_features: Whether to create spatial features from lat/lon
        
    Returns:
        DataFrame with all engineered features
    """
    print("Starting feature engineering...")
    df = df.copy()
    
    # Sort by sensor and time
    df = df.sort_values([sensor_id_col, time_col]).reset_index(drop=True)
    
    # Normalize weather columns to match training schema (humidity->relative_humidity_2m, etc.)
    df = normalize_weather_schema(df)
    
    # 0. Ensure wind direction features exist (create from wdir if missing)
    if 'wdir' in df.columns:
        if 'wind_dir_x' not in df.columns or 'wind_dir_y' not in df.columns:
            mask = df['wdir'].notna()
            if mask.any():
                df.loc[mask, 'wind_dir_x'] = np.cos(np.radians(df.loc[mask, 'wdir']))
                df.loc[mask, 'wind_dir_y'] = np.sin(np.radians(df.loc[mask, 'wdir']))
        # Ensure wind features exist even if wdir is missing (fill with 0 to match training)
        if 'wind_dir_x' not in df.columns:
            df['wind_dir_x'] = 0.0
        if 'wind_dir_y' not in df.columns:
            df['wind_dir_y'] = 0.0
    else:
        # No wind data - create zero-filled columns to match training behavior
        df['wdir'] = 0.0
        df['wind_dir_x'] = 0.0
        df['wind_dir_y'] = 0.0
    
    # 0. Create spatial features (before time series features, since they're static per sensor)
    if include_spatial_features:
        print("Creating spatial features...")
        df = create_spatial_features(df, sensor_id_col)
    
    # 1. Create time features
    print("Creating time features...")
    df = create_time_features(df, time_col)
    
    # 2. Create lag features (must match training: relative_humidity_2m, temperature_2m)
    print("Creating lag features...")
    df = create_lag_features(df, sensor_id_col, 
                            value_cols=['pm2_5_atm', 'relative_humidity_2m', 'temperature_2m'],
                            lags=[1, 2, 3, 4, 6, 12])
    
    # 3. Create rolling features (must match training)
    print("Creating rolling features...")
    df = create_rolling_features(df, sensor_id_col,
                                value_cols=['pm2_5_atm', 'relative_humidity_2m', 'temperature_2m'],
                                windows=[2, 4, 6, 12, 24])
    
    # 4. Create spatial interaction features (after we have PM2.5 data)
    if include_spatial_features and 'latitude' in df.columns:
        print("Creating spatial interaction features...")
        try:
            df = create_spatial_interaction_features(df, sensor_id_col)
        except ImportError:
            print("Warning: scipy not available. Skipping spatial interaction features.")
        except Exception as e:
            print(f"Warning: Could not create spatial interaction features: {e}")
    
    # Ensure spatial interaction features exist (even if only one sensor or creation failed)
    if 'pm25_nearby_sensors_avg' not in df.columns:
        df['pm25_nearby_sensors_avg'] = df['pm2_5_atm'].fillna(0)
    if 'pm25_nearby_sensors_std' not in df.columns:
        df['pm25_nearby_sensors_std'] = 0.0
    
    # Fill any remaining NaN values in spatial interaction features
    df['pm25_nearby_sensors_avg'] = df['pm25_nearby_sensors_avg'].fillna(df['pm2_5_atm'].fillna(0))
    df['pm25_nearby_sensors_std'] = df['pm25_nearby_sensors_std'].fillna(0.0)
    
    # 5. Create targets if requested
    if include_targets:
        print("Creating target variables...")
        df = create_targets(df, sensor_id_col, target_col='pm2_5_atm', 
                           forecast_horizons=[2, 6])
    
    # Remove rows where targets are NaN (end of time series for each sensor)
    if include_targets:
        target_cols = [col for col in df.columns if '_target_' in col]
        initial_rows = len(df)
        df = df.dropna(subset=target_cols)
        removed = initial_rows - len(df)
        if removed > 0:
            print(f"Removed {removed} rows with missing targets (end of time series)")
    
    # Remove infinite values
    df = df.replace([np.inf, -np.inf], np.nan)
    # Fix A: weather-only ffill within sensor (no bfill, no cross-sensor, matches training)
    weather_cols = ['temperature_2m', 'relative_humidity_2m', 'wind_speed_10m', 
                    'wind_direction_10m', 'wdir', 'wind_dir_x', 'wind_dir_y']
    for col in weather_cols:
        if col in df.columns:
            df[col] = df.groupby(sensor_id_col)[col].transform('ffill')
    df = df.fillna(0)  # Fill any remaining NaNs with 0
    
    print(f"Feature engineering complete. Final shape: {df.shape}")
    return df


if __name__ == "__main__":
    # Test feature engineering
    import os
    from data_preprocessing import load_sensor_data, clean_data
    from aqi_utils import add_aqi_to_dataframe
    
    data_dir = os.path.dirname(os.path.abspath(__file__))
    df = load_sensor_data(data_dir)
    df = clean_data(df)
    df = add_aqi_to_dataframe(df)
    
    # Get data for one sensor for testing
    test_sensor = df[df['sensor_id'] == df['sensor_id'].iloc[0]].head(100).copy()
    test_df = engineer_features(test_sensor)
    
    print(f"\nFeature columns: {len(test_df.columns)}")
    print(f"\nSample features:\n{test_df[['sensor_id', 'time_stamp', 'pm2_5_atm', 'pm2_5_atm_lag_1', 'pm2_5_atm_rolling_mean_2', 'hour', 'day_of_week']].head()}")

