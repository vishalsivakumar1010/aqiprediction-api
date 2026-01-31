"""
Phase 2: Step 5 - Feature Engineering
Creates lag features, rolling statistics, time features, spatial features, and wind encoding.
Uses Open-Meteo weather data (temperature_2m, relative_humidity_2m) instead of PurpleAir.
"""

import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))


def create_time_features(df, time_col='time_stamp'):
    """Extract time-based features from timestamp column."""
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    
    # Extract time components
    df['hour'] = df[time_col].dt.hour
    df['day_of_week'] = df[time_col].dt.dayofweek  # 0=Monday, 6=Sunday
    df['day_of_month'] = df[time_col].dt.day
    df['month'] = df[time_col].dt.month
    df['day_of_year'] = df[time_col].dt.dayofyear
    
    # Cyclical encoding for periodic features
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['day_of_week_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
    df['day_of_week_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
    df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
    df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
    
    return df


def create_lag_features(df, sensor_id_col='sensor_id', 
                       value_cols=['pm2_5_atm', 'relative_humidity_2m', 'temperature_2m'],
                       lags=[1, 2, 3, 4, 6, 12]):
    """
    Create lagged features for each sensor separately.
    Uses only past values (no data leakage).
    """
    df = df.copy()
    df = df.sort_values([sensor_id_col, 'time_stamp']).reset_index(drop=True)
    
    for sensor_id in df[sensor_id_col].unique():
        sensor_mask = df[sensor_id_col] == sensor_id
        sensor_data = df[sensor_mask].copy()
        
        for col in value_cols:
            if col not in df.columns:
                continue
            for lag in lags:
                lag_col_name = f'{col}_lag_{lag}'
                df.loc[sensor_mask, lag_col_name] = sensor_data[col].shift(lag).values
        
        # Also create difference features
        for col in value_cols:
            if col not in df.columns:
                continue
            diff_col_name = f'{col}_diff'
            df.loc[sensor_mask, diff_col_name] = sensor_data[col].diff().values
    
    return df


def create_rolling_features(df, sensor_id_col='sensor_id',
                           value_cols=['pm2_5_atm', 'relative_humidity_2m', 'temperature_2m'],
                           windows=[2, 4, 6, 12, 24]):
    """
    Create rolling statistics using ONLY past values (t-1, t-2, ...) to avoid data leakage.
    """
    df = df.copy()
    df = df.sort_values([sensor_id_col, 'time_stamp']).reset_index(drop=True)
    
    for sensor_id in df[sensor_id_col].unique():
        sensor_mask = df[sensor_id_col] == sensor_id
        sensor_data = df[sensor_mask].copy()
        
        for col in value_cols:
            if col not in df.columns:
                continue
            for window in windows:
                # CRITICAL: Shift by 1 to exclude current value
                shifted_values = sensor_data[col].shift(1)
                
                # Rolling mean
                mean_col = f'{col}_rolling_mean_{window}'
                df.loc[sensor_mask, mean_col] = shifted_values.rolling(window=window, min_periods=1).mean().values
                
                # Rolling std
                std_col = f'{col}_rolling_std_{window}'
                df.loc[sensor_mask, std_col] = shifted_values.rolling(window=window, min_periods=1).std().values
                
                # Rolling min
                min_col = f'{col}_rolling_min_{window}'
                df.loc[sensor_mask, min_col] = shifted_values.rolling(window=window, min_periods=1).min().values
                
                # Rolling max
                max_col = f'{col}_rolling_max_{window}'
                df.loc[sensor_mask, max_col] = shifted_values.rolling(window=window, min_periods=1).max().values
    
    return df


def create_spatial_features(df, sensor_id_col='sensor_id'):
    """Create spatial features from latitude and longitude."""
    df = df.copy()
    
    if 'latitude' not in df.columns or 'longitude' not in df.columns:
        print("Warning: Latitude/longitude not found. Skipping spatial features.")
        return df
    
    if df['latitude'].notna().any() and df['longitude'].notna().any():
        center_lat = df['latitude'].mean()
        center_lon = df['longitude'].mean()
        
        # Distance from center
        df['distance_from_center_km'] = np.sqrt(
            ((df['latitude'] - center_lat) * 111) ** 2 +
            ((df['longitude'] - center_lon) * 111 * np.cos(np.radians(center_lat))) ** 2
        )
        
        # Normalized coordinates
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
        
        # Coordinate interactions
        df['lat_lon_product'] = df['latitude'] * df['longitude']
        df['lat_squared'] = df['latitude'] ** 2
        df['lon_squared'] = df['longitude'] ** 2
    
    return df


def create_spatial_interaction_features(df, sensor_id_col='sensor_id'):
    """Create features based on spatial interactions between sensors."""
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
    
    # Calculate pairwise distances
    coords = sensor_locations[['latitude', 'longitude']].values
    sensor_ids = sensor_locations[sensor_id_col].values
    
    center_lat = coords[:, 0].mean()
    coords_km = np.column_stack([
        (coords[:, 0] - center_lat) * 111,
        (coords[:, 1] - coords[:, 1].mean()) * 111 * np.cos(np.radians(center_lat))
    ])
    
    distances = cdist(coords_km, coords_km)
    
    # Find nearby sensors (within 5km)
    nearby_sensor_map = {}
    for idx, sensor_id in enumerate(sensor_ids):
        nearby_indices = np.where((distances[idx] < 5) & (distances[idx] > 0))[0]
        if len(nearby_indices) > 0:
            nearby_sensor_map[sensor_id] = sensor_ids[nearby_indices].tolist()
    
    # Initialize columns
    df['pm25_nearby_sensors_avg'] = np.nan
    df['pm25_nearby_sensors_std'] = np.nan
    
    # Calculate for each timestamp
    for time_stamp in df['time_stamp'].unique():
        time_mask = df['time_stamp'] == time_stamp
        time_data = df[time_mask].copy()
        
        for sensor_id in time_data[sensor_id_col].unique():
            sensor_mask = (df[sensor_id_col] == sensor_id) & time_mask
            
            if sensor_id in nearby_sensor_map:
                nearby_ids = nearby_sensor_map[sensor_id]
                nearby_pm25 = time_data[time_data[sensor_id_col].isin(nearby_ids)]['pm2_5_atm'].dropna().values
                
                if len(nearby_pm25) > 0:
                    df.loc[sensor_mask, 'pm25_nearby_sensors_avg'] = np.mean(nearby_pm25)
                    df.loc[sensor_mask, 'pm25_nearby_sensors_std'] = np.std(nearby_pm25) if len(nearby_pm25) > 1 else 0
    
    # Fill NaN values
    df['pm25_nearby_sensors_avg'] = df['pm25_nearby_sensors_avg'].fillna(df['pm2_5_atm'])
    df['pm25_nearby_sensors_std'] = df['pm25_nearby_sensors_std'].fillna(0)
    
    return df


def create_targets(df, sensor_id_col='sensor_id', target_col='pm2_5_atm',
                   forecast_horizons=[2, 6]):
    """
    Create target variables for 1-hour (2 steps) and 3-hour (6 steps) ahead predictions.
    """
    df = df.copy()
    df = df.sort_values([sensor_id_col, 'time_stamp']).reset_index(drop=True)
    
    for horizon in forecast_horizons:
        target_col_name = f'{target_col}_target_{horizon}h'
        
        for sensor_id in df[sensor_id_col].unique():
            sensor_mask = df[sensor_id_col] == sensor_id
            sensor_data = df[sensor_mask].copy()
            
            df.loc[sensor_mask, target_col_name] = sensor_data[target_col].shift(-horizon).values
    
    return df


def engineer_features(df, sensor_id_col='sensor_id', time_col='time_stamp',
                     include_targets=True, include_spatial_features=True):
    """
    Complete feature engineering pipeline for Phase 2.
    Uses Open-Meteo weather data (temperature_2m, relative_humidity_2m).
    """
    print("Starting feature engineering...")
    df = df.copy()
    
    # Sort by sensor and time
    df = df.sort_values([sensor_id_col, time_col]).reset_index(drop=True)
    
    # Ensure wind direction features exist
    if 'wdir' in df.columns:
        mask = df['wdir'].notna()
        if mask.any():
            df.loc[mask, 'wind_dir_x'] = np.cos(np.radians(df.loc[mask, 'wdir']))
            df.loc[mask, 'wind_dir_y'] = np.sin(np.radians(df.loc[mask, 'wdir']))
        if 'wind_dir_x' not in df.columns:
            df['wind_dir_x'] = 0.0
        if 'wind_dir_y' not in df.columns:
            df['wind_dir_y'] = 0.0
    else:
        df['wdir'] = 0.0
        df['wind_dir_x'] = 0.0
        df['wind_dir_y'] = 0.0
    
    # Create spatial features (static per sensor)
    if include_spatial_features:
        print("Creating spatial features...")
        df = create_spatial_features(df, sensor_id_col)
    
    # Create time features
    print("Creating time features...")
    df = create_time_features(df, time_col)
    
    # Create lag features (using Open-Meteo weather columns)
    print("Creating lag features...")
    df = create_lag_features(df, sensor_id_col,
                            value_cols=['pm2_5_atm', 'relative_humidity_2m', 'temperature_2m'],
                            lags=[1, 2, 3, 4, 6, 12])
    
    # Create rolling features
    print("Creating rolling features...")
    df = create_rolling_features(df, sensor_id_col,
                                value_cols=['pm2_5_atm', 'relative_humidity_2m', 'temperature_2m'],
                                windows=[2, 4, 6, 12, 24])
    
    # Create spatial interaction features
    if include_spatial_features and 'latitude' in df.columns:
        print("Creating spatial interaction features...")
        try:
            df = create_spatial_interaction_features(df, sensor_id_col)
        except ImportError:
            print("Warning: scipy not available. Skipping spatial interaction features.")
        except Exception as e:
            print(f"Warning: Could not create spatial interaction features: {e}")
    
    # Ensure spatial interaction features exist
    if 'pm25_nearby_sensors_avg' not in df.columns:
        df['pm25_nearby_sensors_avg'] = df['pm2_5_atm'].fillna(0)
    if 'pm25_nearby_sensors_std' not in df.columns:
        df['pm25_nearby_sensors_std'] = 0.0
    
    df['pm25_nearby_sensors_avg'] = df['pm25_nearby_sensors_avg'].fillna(df['pm2_5_atm'].fillna(0))
    df['pm25_nearby_sensors_std'] = df['pm25_nearby_sensors_std'].fillna(0.0)
    
    # Create targets if requested
    if include_targets:
        print("Creating target variables...")
        df = create_targets(df, sensor_id_col, target_col='pm2_5_atm',
                           forecast_horizons=[2, 6])
    
    # Remove rows where targets are NaN
    if include_targets:
        target_cols = [col for col in df.columns if '_target_' in col]
        initial_rows = len(df)
        df = df.dropna(subset=target_cols)
        removed = initial_rows - len(df)
        if removed > 0:
            print(f"Removed {removed} rows with missing targets (end of time series)")
    
    # Remove infinite values and fill NaNs
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.bfill().ffill()
    df = df.fillna(0)
    
    print(f"Feature engineering complete. Final shape: {df.shape}")
    return df


def main():
    """Main execution function."""
    # Paths
    input_file = Path(__file__).parent.parent / "data" / "processed" / "purpleair_with_weather.csv"
    output_dir = Path(__file__).parent.parent / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("="*70)
    print("PHASE 2: FEATURE ENGINEERING")
    print("="*70)
    
    # Load merged data
    print(f"\nLoading merged data from: {input_file}")
    df = pd.read_csv(input_file, parse_dates=['time_stamp'])
    print(f"Loaded {len(df):,} rows")
    
    # Engineer features
    df_features = engineer_features(df, include_targets=True, include_spatial_features=True)
    
    # Save feature-engineered data
    output_file = output_dir / "dataset_with_features.csv"
    df_features.to_csv(output_file, index=False)
    
    print(f"\n{'='*70}")
    print("COMPLETE")
    print(f"{'='*70}")
    print(f"\nFeature-engineered data saved to: {output_file}")
    print(f"Final size: {len(df_features):,} rows, {len(df_features.columns)} columns")
    
    # Summary
    print(f"\nFeature summary:")
    print(f"  Time features: {len([c for c in df_features.columns if c in ['hour', 'day_of_week', 'month', 'hour_sin', 'hour_cos']])}")
    print(f"  Lag features: {len([c for c in df_features.columns if '_lag_' in c])}")
    print(f"  Rolling features: {len([c for c in df_features.columns if '_rolling_' in c])}")
    print(f"  Spatial features: {len([c for c in df_features.columns if 'latitude' in c or 'longitude' in c or 'distance' in c or 'nearby' in c])}")
    print(f"  Wind features: {len([c for c in df_features.columns if 'wind' in c or 'wdir' in c])}")
    print(f"  Target features: {len([c for c in df_features.columns if '_target_' in c])}")


if __name__ == "__main__":
    main()
