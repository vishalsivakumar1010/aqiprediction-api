"""
Validate predictions against historical data.

This script:
1. Loads historical data from CSV files
2. Picks a "current" timestamp from the past
3. Makes predictions for 1h and 3h ahead
4. Compares predictions to actual values that occurred at those future times
5. Calculates error metrics (MAE, RMSE, bias)

Usage:
    python3 validate_historic_data.py --sensor-id 17895 --start-date "2025-06-01" --num-tests 50
"""

import pandas as pd
import numpy as np
import os
import sys
import argparse
from datetime import datetime, timedelta
import warnings
import glob

warnings.filterwarnings('ignore')

# Add path to original pipeline for imports
original_pipeline_dir = os.path.expanduser("~/Downloads/PAIC Data 2 Months")
if os.path.exists(original_pipeline_dir) and original_pipeline_dir not in sys.path:
    sys.path.insert(0, original_pipeline_dir)

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from test_predictions import (
        load_models, load_sensor_locations, prepare_features_for_prediction,
        make_predictions, prepare_test_data_from_csv, fetch_current_wind_data_for_prediction,
        merge_wind_data_for_prediction, WIND_FETCHING_AVAILABLE
    )
    from aqi_utils import pm25_to_aqi, aqi_to_category
except ImportError as e:
    print(f"Error: Could not import required modules: {e}")
    sys.exit(1)


def load_sensor_csv(data_dir, sensor_id):
    """
    Load full historical CSV file for a sensor.
    
    Returns:
        DataFrame with all historical data, or None if file not found
    """
    csv_pattern = os.path.join(data_dir, f"{sensor_id} *30-Minute Average.csv")
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
    
    # Sort by time
    df = df.sort_values('time_stamp').reset_index(drop=True)
    
    return df


def get_actual_future_value(df, current_index, horizon_steps):
    """
    Get actual PM2.5 value that occurred at horizon_steps in the future.
    
    Args:
        df: DataFrame with historical data
        current_index: Index of current timestamp
        horizon_steps: Number of 30-minute steps ahead (2 for 1h, 6 for 3h)
        
    Returns:
        Actual PM2.5 value at future time, or None if not available
    """
    future_index = current_index + horizon_steps
    if future_index < len(df):
        return df.iloc[future_index]['pm2_5_atm']
    return None


def validate_single_timestamp(data_dir, sensor_id, current_timestamp, models):
    """
    Validate prediction for a single historical timestamp.
    
    Args:
        data_dir: Directory containing CSV files
        sensor_id: Sensor ID
        current_timestamp: Timestamp to treat as "current"
        models: Loaded model dictionary
        
    Returns:
        Dictionary with validation results, or None if validation failed
    """
    try:
        # Load full historical data
        df_full = load_sensor_csv(data_dir, sensor_id)
        if df_full is None:
            return None
        
        # Find index of current timestamp (within 30 minutes)
        current_timestamp_utc = pd.to_datetime(current_timestamp, utc=True)
        time_diffs = abs(df_full['time_stamp'] - current_timestamp_utc)
        current_idx = time_diffs.idxmin()
        
        if time_diffs.loc[current_idx] > pd.Timedelta(hours=1):
            # Timestamp too far from any data point
            return None
        
        current_row = df_full.iloc[current_idx]
        current_pm25 = current_row['pm2_5_atm']
        current_aqi = pm25_to_aqi(current_pm25)
        
        # Get actual future values (1h = 2 steps, 3h = 6 steps)
        actual_pm25_1h = get_actual_future_value(df_full, current_idx, 2)
        actual_pm25_3h = get_actual_future_value(df_full, current_idx, 6)
        
        if actual_pm25_1h is None or actual_pm25_3h is None:
            return None
        
        actual_aqi_1h = pm25_to_aqi(actual_pm25_1h)
        actual_aqi_3h = pm25_to_aqi(actual_pm25_3h)
        
        # Prepare data up to current timestamp for prediction
        # We need ~48 rows (24 hours) of historical data for features
        start_idx = max(0, current_idx - 47)
        df_for_prediction = df_full.iloc[start_idx:current_idx+1].copy()
        
        # Add location data
        locations_df = load_sensor_locations(data_dir)
        if locations_df is not None:
            sensor_locs = locations_df[locations_df['sensor_id'] == int(sensor_id)]
            if not sensor_locs.empty:
                df_for_prediction['latitude'] = sensor_locs.iloc[0]['latitude']
                df_for_prediction['longitude'] = sensor_locs.iloc[0]['longitude']
        
        # Skip wind data for historical validation (would need Open-Meteo historical API)
        # For now, predictions will proceed without wind features (model was trained with wind, so this may reduce accuracy)
        # TODO: Integrate Open-Meteo historical API for proper wind data in historical validation
        
        # Ensure sensor_id is set
        df_for_prediction['sensor_id'] = int(sensor_id)
        
        # Prepare features
        feature_row = prepare_features_for_prediction(df_for_prediction, sensor_id)
        feature_columns = models['1h']['feature_columns']
        
        # Make predictions with ensemble
        predictions = make_predictions(models, feature_row, feature_columns, current_pm25=current_pm25, ensemble_weight=0.6)
        
        # Calculate errors
        pred_pm25_1h = predictions['1h']['pm25_ugm3']
        pred_pm25_3h = predictions['3h']['pm25_ugm3']
        
        error_1h = pred_pm25_1h - actual_pm25_1h
        error_3h = pred_pm25_3h - actual_pm25_3h
        
        return {
            'timestamp': current_timestamp_utc,
            'current_pm25': current_pm25,
            'current_aqi': current_aqi,
            'pred_pm25_1h': pred_pm25_1h,
            'actual_pm25_1h': actual_pm25_1h,
            'error_1h': error_1h,
            'pred_aqi_1h': predictions['1h']['aqi'],
            'actual_aqi_1h': actual_aqi_1h,
            'pred_pm25_3h': pred_pm25_3h,
            'actual_pm25_3h': actual_pm25_3h,
            'error_3h': error_3h,
            'pred_aqi_3h': predictions['3h']['aqi'],
            'actual_aqi_3h': actual_aqi_3h,
            'success': True
        }
        
    except Exception as e:
        print(f"Error validating timestamp {current_timestamp}: {e}")
        return {'success': False, 'error': str(e)}


def validate_historical_predictions(data_dir, sensor_id, start_date, end_date, num_tests, models):
    """
    Validate predictions across multiple historical timestamps.
    
    Args:
        data_dir: Directory containing CSV files
        sensor_id: Sensor ID
        start_date: Start date for validation (YYYY-MM-DD)
        end_date: End date for validation (YYYY-MM-DD)
        num_tests: Number of timestamps to test
        models: Loaded model dictionary
        
    Returns:
        DataFrame with validation results
    """
    # Load full data to find available timestamps
    df_full = load_sensor_csv(data_dir, sensor_id)
    if df_full is None:
        print(f"Error: Could not load CSV file for sensor {sensor_id}")
        return None
    
    # Filter by date range
    start_dt = pd.to_datetime(start_date, utc=True)
    end_dt = pd.to_datetime(end_date, utc=True)
    df_filtered = df_full[(df_full['time_stamp'] >= start_dt) & (df_full['time_stamp'] <= end_dt)].copy()
    
    if len(df_filtered) < num_tests:
        print(f"Warning: Only {len(df_filtered)} timestamps available, using all")
        num_tests = len(df_filtered)
    
    # Sample timestamps evenly across the range
    # Leave enough room at the end for 3h future predictions
    max_idx = len(df_filtered) - 7  # Need at least 6 steps (3h) for future
    if max_idx < 0:
        print("Error: Not enough data points for validation")
        return None
    
    step = max(1, max_idx // num_tests)
    test_indices = list(range(48, min(len(df_filtered) - 7, 48 + num_tests * step), step))[:num_tests]
    
    results = []
    print(f"\nValidating {len(test_indices)} timestamps...")
    
    for i, idx in enumerate(test_indices):
        test_timestamp = df_filtered.iloc[idx]['time_stamp']
        print(f"  [{i+1}/{len(test_indices)}] Testing {test_timestamp}...", end=' ', flush=True)
        
        result = validate_single_timestamp(data_dir, sensor_id, test_timestamp, models)
        
        if result and result.get('success'):
            results.append(result)
            print(f"✓ (Error 1h: {result['error_1h']:.2f}, 3h: {result['error_3h']:.2f})")
        else:
            print(f"✗ Failed")
    
    if not results:
        print("\nError: No successful validations")
        return None
    
    # Create results DataFrame
    results_df = pd.DataFrame(results)
    
    # Calculate summary statistics
    print(f"\n{'='*80}")
    print(f"VALIDATION RESULTS")
    print(f"{'='*80}")
    print(f"\nTotal validations: {len(results_df)}")
    
    for horizon in ['1h', '3h']:
        error_col = f'error_{horizon}'
        pred_col = f'pred_pm25_{horizon}'
        actual_col = f'actual_pm25_{horizon}'
        
        errors = results_df[error_col]
        mae = errors.abs().mean()
        rmse = np.sqrt((errors ** 2).mean())
        bias = errors.mean()
        
        print(f"\n{horizon.upper()} Forecast Performance:")
        print(f"  MAE:  {mae:.2f} μg/m³")
        print(f"  RMSE: {rmse:.2f} μg/m³")
        print(f"  Bias: {bias:.2f} μg/m³ ({'over-predicting' if bias > 0 else 'under-predicting' if bias < 0 else 'unbiased'})")
        
        # Category accuracy
        pred_cat_col = f'pred_aqi_{horizon}'
        actual_cat_col = f'actual_aqi_{horizon}'
        if pred_cat_col in results_df.columns and actual_cat_col in results_df.columns:
            # Calculate category from AQI
            results_df[f'pred_category_{horizon}'] = results_df[pred_cat_col].apply(aqi_to_category)
            results_df[f'actual_category_{horizon}'] = results_df[actual_cat_col].apply(aqi_to_category)
            cat_accuracy = (results_df[f'pred_category_{horizon}'] == results_df[f'actual_category_{horizon}']).mean()
            print(f"  Category Accuracy: {cat_accuracy*100:.1f}%")
    
    return results_df


def main():
    parser = argparse.ArgumentParser(description='Validate predictions against historical data')
    parser.add_argument('--sensor-id', type=int, required=True, help='Sensor ID to validate')
    parser.add_argument('--data-dir', type=str, default=None, help='Directory containing CSV files')
    parser.add_argument('--model-dir', type=str, default='models', help='Directory containing trained models')
    parser.add_argument('--start-date', type=str, default='2025-06-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default='2025-12-31', help='End date (YYYY-MM-DD)')
    parser.add_argument('--num-tests', type=int, default=50, help='Number of timestamps to test')
    parser.add_argument('--output', type=str, default=None, help='Output CSV file for results')
    
    args = parser.parse_args()
    
    # Determine data directory
    if args.data_dir is None:
        data_dir = os.path.dirname(os.path.abspath(__file__))
    else:
        data_dir = args.data_dir
    
    # Load models
    print("Loading models...")
    try:
        models = load_models(args.model_dir)
        print(f"✓ Models loaded")
    except Exception as e:
        print(f"✗ Error loading models: {e}")
        sys.exit(1)
    
    # Run validation
    results_df = validate_historical_predictions(
        data_dir, args.sensor_id, args.start_date, args.end_date, args.num_tests, models
    )
    
    if results_df is not None and len(results_df) > 0:
        # Save results
        if args.output:
            results_df.to_csv(args.output, index=False)
            print(f"\n✓ Results saved to: {args.output}")
        else:
            output_file = f"validation_historic_{args.sensor_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            results_df.to_csv(output_file, index=False)
            print(f"\n✓ Results saved to: {output_file}")
    else:
        print("\n✗ Validation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
