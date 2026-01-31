"""
Phase 2: Historical Validation for v2 Model
Validates v2 model predictions against historical data from specific sensors.
Similar to v1 validation but uses v2 models and Open-Meteo weather data.
"""

import pandas as pd
import numpy as np
import os
import sys
import pickle
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import warnings
import glob

warnings.filterwarnings('ignore')

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import AQI utilities
try:
    from aqi_utils import pm25_to_aqi, aqi_to_category
except ImportError:
    # Fallback AQI conversion
    def pm25_to_aqi(pm25):
        pm25 = np.array(pm25)
        aqi = np.where(pm25 <= 12.0, (pm25 / 12.0) * 50,
              np.where(pm25 <= 35.4, ((pm25 - 12.1) / (35.4 - 12.1)) * 50 + 50,
              np.where(pm25 <= 55.4, ((pm25 - 35.5) / (55.4 - 35.5)) * 50 + 100,
              np.where(pm25 <= 150.4, ((pm25 - 55.5) / (150.4 - 55.5)) * 50 + 150,
              np.where(pm25 <= 250.4, ((pm25 - 150.5) / (250.4 - 150.5)) * 100 + 200,
              ((pm25 - 250.5) / (350.4 - 250.5)) * 100 + 300)))))
        return aqi
    
    def aqi_to_category(aqi):
        aqi = np.array(aqi)
        return np.where(aqi <= 50, 'Good',
               np.where(aqi <= 100, 'Moderate',
               np.where(aqi <= 150, 'Unhealthy for Sensitive Groups',
               np.where(aqi <= 200, 'Unhealthy',
               np.where(aqi <= 300, 'Very Unhealthy', 'Hazardous')))))


def load_v2_models(model_dir):
    """Load v2 models for 1h and 3h horizons."""
    models = {}
    
    for horizon in [1, 3]:
        regressor_file = os.path.join(model_dir, f'xgboost_regressor_{horizon}h.pkl')
        classifier_file = os.path.join(model_dir, f'xgboost_classifier_{horizon}h.pkl')
        feature_cols_file = os.path.join(model_dir, f'feature_columns_{horizon}h.pkl')
        
        if not all(os.path.exists(f) for f in [regressor_file, classifier_file, feature_cols_file]):
            raise FileNotFoundError(f"Missing model files for {horizon}h horizon")
        
        with open(regressor_file, 'rb') as f:
            regressor = pickle.load(f)
        with open(classifier_file, 'rb') as f:
            classifier = pickle.load(f)
        with open(feature_cols_file, 'rb') as f:
            feature_cols = pickle.load(f)
        
        models[f'{horizon}h'] = {
            'regressor': regressor,
            'classifier': classifier,
            'feature_columns': feature_cols
        }
    
    return models


def load_sensor_csv(purpleair_dir, sensor_id):
    """Load full historical CSV file for a sensor."""
    csv_pattern = os.path.join(purpleair_dir, f"{sensor_id} *30-Minute Average.csv")
    csv_files = glob.glob(csv_pattern)
    
    if not csv_files:
        return None
    
    csv_file = csv_files[0]
    df = pd.read_csv(csv_file)
    
    # Standardize column names
    if 'pm2.5_atm' in df.columns:
        df = df.rename(columns={'pm2.5_atm': 'pm2_5_atm'})
    
    # Convert timestamp
    df['time_stamp'] = pd.to_datetime(df['time_stamp'], utc=True)
    if df['time_stamp'].dt.tz is not None:
        df['time_stamp'] = df['time_stamp'].dt.tz_convert('America/Los_Angeles').dt.tz_localize(None)
    
    # Sort by time
    df = df.sort_values('time_stamp').reset_index(drop=True)
    
    return df


def load_openmeteo_weather(weather_file):
    """Load Open-Meteo weather data."""
    df = pd.read_csv(weather_file, skiprows=3)
    df.columns = df.columns.str.strip()
    df['time'] = pd.to_datetime(df['time'])
    
    # Rename columns
    column_mapping = {
        'temperature_2m (°F)': 'temperature_2m',
        'relative_humidity_2m (%)': 'relative_humidity_2m',
        'wind_speed_10m (mp/h)': 'wind_speed_10m',
        'wind_direction_10m (°)': 'wind_direction_10m'
    }
    
    for old_col, new_col in column_mapping.items():
        if old_col in df.columns:
            df = df.rename(columns={old_col: new_col})
    
    # Convert to PST (timezone-naive)
    if df['time'].dt.tz is not None:
        df['time'] = df['time'].dt.tz_convert('America/Los_Angeles').dt.tz_localize(None)
    
    df = df.sort_values('time').reset_index(drop=True)
    return df


def merge_weather_for_timestamp(df_sensor, df_weather, timestamp):
    """Merge weather data for a specific timestamp."""
    # Round to nearest hour
    hour_timestamp = timestamp.floor('H')
    
    # Find matching weather row
    weather_row = df_weather[df_weather['time'] == hour_timestamp]
    
    if weather_row.empty:
        # Try to find nearest hour
        time_diffs = abs(df_weather['time'] - hour_timestamp)
        nearest_idx = time_diffs.idxmin()
        if time_diffs.loc[nearest_idx] <= pd.Timedelta(hours=2):
            weather_row = df_weather.iloc[[nearest_idx]]
        else:
            return None
    
    if weather_row.empty:
        return None
    
    # Merge weather columns
    weather_data = weather_row.iloc[0]
    df_sensor['temperature_2m'] = weather_data['temperature_2m']
    df_sensor['relative_humidity_2m'] = weather_data['relative_humidity_2m']
    df_sensor['wind_speed_10m'] = weather_data['wind_speed_10m']
    df_sensor['wind_direction_10m'] = weather_data['wind_direction_10m']
    
    # Calculate wind direction components
    wdir = weather_data['wind_direction_10m']
    df_sensor['wdir'] = wdir
    df_sensor['wind_dir_x'] = np.cos(np.radians(wdir))
    df_sensor['wind_dir_y'] = np.sin(np.radians(wdir))
    
    return df_sensor


def prepare_features_v2(df_sensor, sensor_id, sensor_locations_df):
    """
    Prepare features for v2 model prediction.
    Uses the same feature engineering as training but simplified for single-sensor prediction.
    """
    # Import feature engineering functions from the scripts directory
    scripts_dir = Path(__file__).parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    
    # Import directly from the module file
    import importlib.util
    fe_path = scripts_dir / "05_feature_engineering.py"
    spec = importlib.util.spec_from_file_location("feature_engineering", fe_path)
    fe_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fe_module)
    
    create_time_features = fe_module.create_time_features
    create_lag_features = fe_module.create_lag_features
    create_rolling_features = fe_module.create_rolling_features
    create_spatial_features = fe_module.create_spatial_features
    
    # Add sensor location
    sensor_info = sensor_locations_df[sensor_locations_df['sensor_id'] == int(sensor_id)]
    if not sensor_info.empty:
        df_sensor['latitude'] = sensor_info.iloc[0]['latitude']
        df_sensor['longitude'] = sensor_info.iloc[0]['longitude']
    else:
        df_sensor['latitude'] = np.nan
        df_sensor['longitude'] = np.nan
    
    # Create features (simplified - only what we can compute from single sensor)
    df_sensor = create_time_features(df_sensor, 'time_stamp')
    df_sensor = create_lag_features(df_sensor, 'sensor_id',
                                   value_cols=['pm2_5_atm', 'relative_humidity_2m', 'temperature_2m'],
                                   lags=[1, 2, 3, 4, 6, 12])
    df_sensor = create_rolling_features(df_sensor, 'sensor_id',
                                       value_cols=['pm2_5_atm', 'relative_humidity_2m', 'temperature_2m'],
                                       windows=[2, 4, 6, 12, 24])
    df_sensor = create_spatial_features(df_sensor, 'sensor_id')
    
    # Add spatial interaction features (simplified - use own value)
    df_sensor['pm25_nearby_sensors_avg'] = df_sensor['pm2_5_atm']
    df_sensor['pm25_nearby_sensors_std'] = 0.0
    
    # Fill NaN values
    df_sensor = df_sensor.fillna(0)
    df_sensor = df_sensor.replace([np.inf, -np.inf], 0)
    
    return df_sensor


def make_prediction_v2(df_features, models, horizon_hours):
    """Make prediction using v2 model."""
    model_key = f'{horizon_hours}h'
    if model_key not in models:
        return None
    
    model_info = models[model_key]
    feature_cols = model_info['feature_columns']
    regressor = model_info['regressor']
    
    # Get features for last row
    last_row = df_features.iloc[[-1]]
    
    # Ensure all required features exist
    missing_cols = [col for col in feature_cols if col not in last_row.columns]
    if missing_cols:
        for col in missing_cols:
            last_row[col] = 0.0
    
    # Select features in correct order
    X = last_row[feature_cols].values
    
    # Predict PM2.5
    pm25_pred = regressor.predict(X)[0]
    
    return pm25_pred


def validate_single_timestamp(purpleair_dir, weather_file, sensor_id, sensor_locations_df,
                              current_timestamp, models):
    """Validate prediction for a single historical timestamp."""
    try:
        # Load sensor data
        df_full = load_sensor_csv(purpleair_dir, sensor_id)
        if df_full is None:
            return None
        
        # Find current timestamp
        current_timestamp_pst = pd.to_datetime(current_timestamp)
        if current_timestamp_pst.tz is not None:
            current_timestamp_pst = current_timestamp_pst.tz_convert('America/Los_Angeles').dt.tz_localize(None)
        
        time_diffs = abs(df_full['time_stamp'] - current_timestamp_pst)
        current_idx = time_diffs.idxmin()
        
        if time_diffs.loc[current_idx] > pd.Timedelta(hours=1):
            return None
        
        current_row = df_full.iloc[current_idx]
        current_pm25 = current_row['pm2_5_atm']
        current_aqi = pm25_to_aqi(current_pm25)
        
        # Get actual future values
        actual_pm25_1h = df_full.iloc[current_idx + 2]['pm2_5_atm'] if current_idx + 2 < len(df_full) else None
        actual_pm25_3h = df_full.iloc[current_idx + 6]['pm2_5_atm'] if current_idx + 6 < len(df_full) else None
        
        if actual_pm25_1h is None or actual_pm25_3h is None:
            return None
        
        actual_aqi_1h = pm25_to_aqi(actual_pm25_1h)
        actual_aqi_3h = pm25_to_aqi(actual_pm25_3h)
        
        # Prepare historical data for prediction (need ~48 rows for features)
        start_idx = max(0, current_idx - 47)
        df_for_prediction = df_full.iloc[start_idx:current_idx+1].copy()
        
        # Ensure sensor_id is present
        df_for_prediction['sensor_id'] = int(sensor_id)
        
        # Load and merge weather data
        df_weather = load_openmeteo_weather(weather_file)
        df_for_prediction = merge_weather_for_timestamp(df_for_prediction, df_weather, current_timestamp_pst)
        
        if df_for_prediction is None:
            return None
        
        # Prepare features
        df_features = prepare_features_v2(df_for_prediction, sensor_id, sensor_locations_df)
        
        # Make predictions
        pred_pm25_1h = make_prediction_v2(df_features, models, 1)
        pred_pm25_3h = make_prediction_v2(df_features, models, 3)
        
        if pred_pm25_1h is None or pred_pm25_3h is None:
            return None
        
        pred_aqi_1h = pm25_to_aqi(pred_pm25_1h)
        pred_aqi_3h = pm25_to_aqi(pred_pm25_3h)
        
        # Calculate errors
        error_pm25_1h = pred_pm25_1h - actual_pm25_1h
        error_pm25_3h = pred_pm25_3h - actual_pm25_3h
        error_aqi_1h = pred_aqi_1h - actual_aqi_1h
        error_aqi_3h = pred_aqi_3h - actual_aqi_3h
        
        # Category accuracy
        actual_cat_1h = aqi_to_category(actual_aqi_1h)
        pred_cat_1h = aqi_to_category(pred_aqi_1h)
        cat_correct_1h = (actual_cat_1h == pred_cat_1h)
        
        actual_cat_3h = aqi_to_category(actual_aqi_3h)
        pred_cat_3h = aqi_to_category(pred_aqi_3h)
        cat_correct_3h = (actual_cat_3h == pred_cat_3h)
        
        return {
            'sensor_id': sensor_id,
            'timestamp': current_timestamp_pst,
            'current_pm25': current_pm25,
            'current_aqi': current_aqi,
            'actual_pm25_1h': actual_pm25_1h,
            'actual_pm25_3h': actual_pm25_3h,
            'actual_aqi_1h': actual_aqi_1h,
            'actual_aqi_3h': actual_aqi_3h,
            'pred_pm25_1h': pred_pm25_1h,
            'pred_pm25_3h': pred_pm25_3h,
            'pred_aqi_1h': pred_aqi_1h,
            'pred_aqi_3h': pred_aqi_3h,
            'error_pm25_1h': error_pm25_1h,
            'error_pm25_3h': error_pm25_3h,
            'error_aqi_1h': error_aqi_1h,
            'error_aqi_3h': error_aqi_3h,
            'category_correct_1h': cat_correct_1h,
            'category_correct_3h': cat_correct_3h,
            'actual_category_1h': actual_cat_1h,
            'pred_category_1h': pred_cat_1h,
            'actual_category_3h': actual_cat_3h,
            'pred_category_3h': pred_cat_3h
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def validate_historical_predictions(purpleair_dir, weather_file, sensor_locations_df,
                                   sensor_id, start_date, end_date, num_tests, models):
    """Validate predictions across multiple historical timestamps."""
    df_full = load_sensor_csv(purpleair_dir, sensor_id)
    if df_full is None:
        print(f"Error: Could not load CSV file for sensor {sensor_id}")
        return None
    
    # Filter by date range
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    df_filtered = df_full[(df_full['time_stamp'] >= start_dt) & (df_full['time_stamp'] <= end_dt)].copy()
    
    if len(df_filtered) < num_tests:
        print(f"Warning: Only {len(df_filtered)} timestamps available, using all")
        num_tests = len(df_filtered)
    
    # Sample timestamps evenly (leave room for 3h future predictions)
    max_idx = len(df_filtered) - 7
    if max_idx < 0:
        print("Error: Not enough data points for validation")
        return None
    
    step = max(1, max_idx // num_tests)
    test_indices = list(range(48, min(len(df_filtered) - 7, 48 + num_tests * step), step))[:num_tests]
    
    results = []
    print(f"\nValidating {len(test_indices)} timestamps for sensor {sensor_id}...")
    
    for i, idx in enumerate(test_indices):
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i+1}/{len(test_indices)}")
        
        current_timestamp = df_filtered.iloc[idx]['time_stamp']
        try:
            result = validate_single_timestamp(
                purpleair_dir, weather_file, sensor_id, sensor_locations_df,
                current_timestamp, models
            )
            
            if result and 'error' not in result:
                results.append(result)
            elif result and 'error' in result:
                if i < 5:  # Only print first few errors
                    print(f"  Warning: Error at timestamp {current_timestamp}: {result.get('error', 'Unknown')}")
        except Exception as e:
            if i < 5:  # Only print first few errors
                print(f"  Warning: Exception at timestamp {current_timestamp}: {e}")
            continue
    
    if not results:
        print("No valid results obtained")
        return None
    
    results_df = pd.DataFrame(results)
    
    # Calculate summary statistics
    print(f"\n{'='*70}")
    print(f"Validation Results for Sensor {sensor_id}")
    print(f"{'='*70}")
    
    print(f"\n1-Hour Forecast:")
    print(f"  PM2.5 MAE:  {results_df['error_pm25_1h'].abs().mean():.2f} μg/m³")
    print(f"  PM2.5 RMSE: {np.sqrt((results_df['error_pm25_1h']**2).mean()):.2f} μg/m³")
    print(f"  PM2.5 Bias: {results_df['error_pm25_1h'].mean():.2f} μg/m³")
    print(f"  AQI MAE:    {results_df['error_aqi_1h'].abs().mean():.2f} AQI")
    print(f"  Category Accuracy: {results_df['category_correct_1h'].mean()*100:.1f}%")
    
    print(f"\n3-Hour Forecast:")
    print(f"  PM2.5 MAE:  {results_df['error_pm25_3h'].abs().mean():.2f} μg/m³")
    print(f"  PM2.5 RMSE: {np.sqrt((results_df['error_pm25_3h']**2).mean()):.2f} μg/m³")
    print(f"  PM2.5 Bias: {results_df['error_pm25_3h'].mean():.2f} μg/m³")
    print(f"  AQI MAE:    {results_df['error_aqi_3h'].abs().mean():.2f} AQI")
    print(f"  Category Accuracy: {results_df['category_correct_3h'].mean()*100:.1f}%")
    
    return results_df


def main():
    parser = argparse.ArgumentParser(description='Validate v2 model predictions against historical data')
    parser.add_argument('--sensor-id', type=int, required=True, help='Sensor ID to validate')
    parser.add_argument('--purpleair-dir', type=str, 
                       default="/Users/vishalsivakumar/Library/Application Support/com.purpleair.data-download-tool/PurpleAir Download 1-25-2026-Fullset",
                       help='Directory containing PurpleAir CSV files')
    parser.add_argument('--weather-file', type=str,
                       default="/Users/vishalsivakumar/Downloads/open-meteo-37.50N122.00W18m-FinalSet.csv",
                       help='Open-Meteo weather CSV file')
    parser.add_argument('--model-dir', type=str, 
                       default=None,
                       help='Directory containing v2 models')
    parser.add_argument('--start-date', type=str, default='2025-06-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default='2025-12-31', help='End date (YYYY-MM-DD)')
    parser.add_argument('--num-tests', type=int, default=200, help='Number of timestamps to test')
    parser.add_argument('--output', type=str, default=None, help='Output CSV file for results')
    
    args = parser.parse_args()
    
    # Determine model directory
    if args.model_dir is None:
        script_dir = Path(__file__).parent
        model_dir = script_dir.parent / "models" / "v2"
    else:
        model_dir = Path(args.model_dir)
    
    # Load sensor locations
    script_dir = Path(__file__).parent
    sensor_locations_file = script_dir.parent / "data" / "sensor_locations" / "sensor_locations.csv"
    sensor_locations_df = pd.read_csv(sensor_locations_file)
    
    # Load models
    print("Loading v2 models...")
    try:
        models = load_v2_models(model_dir)
        print(f"✓ Models loaded from {model_dir}")
    except Exception as e:
        print(f"✗ Error loading models: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Run validation
    results_df = validate_historical_predictions(
        args.purpleair_dir, args.weather_file, sensor_locations_df,
        args.sensor_id, args.start_date, args.end_date, args.num_tests, models
    )
    
    if results_df is not None and len(results_df) > 0:
        # Save results
        if args.output:
            output_file = args.output
        else:
            output_file = f"validation_historic_v2_{args.sensor_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        results_df.to_csv(output_file, index=False)
        print(f"\n✓ Results saved to: {output_file}")
    else:
        print("\n✗ Validation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
