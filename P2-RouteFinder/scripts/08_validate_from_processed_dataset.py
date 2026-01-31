"""
Phase 2: Validation using Processed Dataset (Apples-to-Apples)
Validates v2 model using the EXACT same processed dataset used for training.
This ensures feature engineering, QC, and data alignment are identical.
"""

import pandas as pd
import numpy as np
import os
import sys
import pickle
import argparse
from pathlib import Path
from datetime import datetime
import warnings
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore')

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import AQI utilities
try:
    from aqi_utils import pm25_to_aqi, aqi_to_category
except ImportError:
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


def target_alignment_sanity_check(df, sensor_id, num_samples=10):
    """
    Sanity check: Print target alignment for random samples.
    Shows t, pm(t), actual timestamp/value for 1h target (t+1h) and 3h target (t+3h).
    """
    sensor_df = df[df['sensor_id'] == int(sensor_id)].copy()
    sensor_df = sensor_df.sort_values('time_stamp').reset_index(drop=True)
    
    # Sample random indices (avoid edges where targets might be missing)
    valid_indices = sensor_df[
        (sensor_df['pm2_5_atm_target_2h'].notna()) & 
        (sensor_df['pm2_5_atm_target_6h'].notna())
    ].index.tolist()
    
    if len(valid_indices) < num_samples:
        num_samples = len(valid_indices)
    
    sample_indices = np.random.choice(valid_indices, size=min(num_samples, len(valid_indices)), replace=False)
    sample_indices = sorted(sample_indices)
    
    print(f"\n{'='*80}")
    print(f"Target Alignment Sanity Check - Sensor {sensor_id}")
    print(f"{'='*80}")
    print(f"{'Index':<8} {'Time (t)':<20} {'PM2.5(t)':<12} {'1h Target Time':<20} {'PM2.5(t+1h)':<12} {'3h Target Time':<20} {'PM2.5(t+3h)':<12}")
    print(f"{'-'*80}")
    
    for idx in sample_indices:
        row = sensor_df.iloc[idx]
        t = row['time_stamp']
        pm_t = row['pm2_5_atm']
        
        # 1h target (2 steps = 1 hour)
        t_1h = sensor_df.iloc[idx + 2]['time_stamp'] if idx + 2 < len(sensor_df) else None
        pm_1h = row['pm2_5_atm_target_2h']
        
        # 3h target (6 steps = 3 hours)
        t_3h = sensor_df.iloc[idx + 6]['time_stamp'] if idx + 6 < len(sensor_df) else None
        pm_3h = row['pm2_5_atm_target_6h']
        
        t_str = str(t)[:19] if pd.notna(t) else "N/A"
        t_1h_str = str(t_1h)[:19] if t_1h is not None else "N/A"
        t_3h_str = str(t_3h)[:19] if t_3h is not None else "N/A"
        
        print(f"{idx:<8} {t_str:<20} {pm_t:>10.2f}  {t_1h_str:<20} {pm_1h:>10.2f}  {t_3h_str:<20} {pm_3h:>10.2f}")
    
    print(f"{'='*80}\n")


def validate_from_processed_dataset(processed_file, model_dir, sensor_ids=None, 
                                    num_samples_per_sensor=2000, start_date='2025-06-01', 
                                    end_date='2025-12-31'):
    """
    Validate using the processed dataset (exact same as training).
    This ensures apples-to-apples comparison.
    """
    print("="*80)
    print("Loading Processed Dataset (Same as Training)")
    print("="*80)
    
    # Load processed dataset
    print(f"Loading: {processed_file}")
    df = pd.read_csv(processed_file, parse_dates=['time_stamp'])
    print(f"Loaded {len(df):,} rows")
    
    # Filter by date range
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    df = df[(df['time_stamp'] >= start_dt) & (df['time_stamp'] <= end_dt)].copy()
    print(f"After date filter: {len(df):,} rows")
    
    # Get available sensors
    if sensor_ids is None:
        sensor_ids = sorted(df['sensor_id'].unique().tolist())
        print(f"Using all {len(sensor_ids)} sensors")
    else:
        sensor_ids = [int(sid) for sid in sensor_ids]
        print(f"Using {len(sensor_ids)} specified sensors")
    
    # Load models
    print(f"\nLoading v2 models from: {model_dir}")
    models = load_v2_models(model_dir)
    print("✓ Models loaded")
    
    # Run target alignment sanity check for first sensor
    if len(sensor_ids) > 0:
        target_alignment_sanity_check(df, sensor_ids[0], num_samples=10)
    
    # Validate each sensor
    all_results = []
    
    for sensor_id in sensor_ids:
        print(f"\n{'='*80}")
        print(f"Validating Sensor {sensor_id}")
        print(f"{'='*80}")
        
        sensor_df = df[df['sensor_id'] == sensor_id].copy()
        sensor_df = sensor_df.sort_values('time_stamp').reset_index(drop=True)
        
        # Filter rows with valid targets
        sensor_df = sensor_df[
            (sensor_df['pm2_5_atm_target_2h'].notna()) & 
            (sensor_df['pm2_5_atm_target_6h'].notna())
        ].copy()
        
        if len(sensor_df) == 0:
            print(f"Warning: No valid rows with targets for sensor {sensor_id}, skipping")
            continue
        
        if len(sensor_df) < num_samples_per_sensor:
            print(f"Warning: Only {len(sensor_df)} valid rows, using all")
            num_samples_per_sensor = len(sensor_df)
        
        # Sample uniformly
        step = max(1, len(sensor_df) // num_samples_per_sensor) if len(sensor_df) > 0 else 1
        sample_indices = list(range(0, len(sensor_df), step))[:num_samples_per_sensor]
        
        print(f"Sampling {len(sample_indices)} rows from {len(sensor_df)} available")
        
        sensor_results = []
        
        for i, idx in enumerate(sample_indices):
            if (i + 1) % 500 == 0:
                print(f"  Progress: {i+1}/{len(sample_indices)}")
            
            row = sensor_df.iloc[idx]
            
            # Get actual targets
            actual_pm25_1h = row['pm2_5_atm_target_2h']
            actual_pm25_3h = row['pm2_5_atm_target_6h']
            
            # Get feature columns
            feature_cols_1h = models['1h']['feature_columns']
            feature_cols_3h = models['3h']['feature_columns']
            
            # Prepare features
            X_1h = row[feature_cols_1h].values.reshape(1, -1)
            X_3h = row[feature_cols_3h].values.reshape(1, -1)
            
            # Make predictions
            pred_pm25_1h = models['1h']['regressor'].predict(X_1h)[0]
            pred_pm25_3h = models['3h']['regressor'].predict(X_3h)[0]
            
            # Calculate metrics
            error_pm25_1h = pred_pm25_1h - actual_pm25_1h
            error_pm25_3h = pred_pm25_3h - actual_pm25_3h
            
            actual_aqi_1h = pm25_to_aqi(actual_pm25_1h)
            pred_aqi_1h = pm25_to_aqi(pred_pm25_1h)
            error_aqi_1h = pred_aqi_1h - actual_aqi_1h
            
            actual_aqi_3h = pm25_to_aqi(actual_pm25_3h)
            pred_aqi_3h = pm25_to_aqi(pred_pm25_3h)
            error_aqi_3h = pred_aqi_3h - actual_aqi_3h
            
            # Category accuracy
            actual_cat_1h = aqi_to_category(actual_aqi_1h)
            pred_cat_1h = aqi_to_category(pred_aqi_1h)
            cat_correct_1h = (actual_cat_1h == pred_cat_1h)
            
            actual_cat_3h = aqi_to_category(actual_aqi_3h)
            pred_cat_3h = aqi_to_category(pred_aqi_3h)
            cat_correct_3h = (actual_cat_3h == pred_cat_3h)
            
            sensor_results.append({
                'sensor_id': sensor_id,
                'timestamp': row['time_stamp'],
                'current_pm25': row['pm2_5_atm'],
                'actual_pm25_1h': actual_pm25_1h,
                'actual_pm25_3h': actual_pm25_3h,
                'pred_pm25_1h': pred_pm25_1h,
                'pred_pm25_3h': pred_pm25_3h,
                'error_pm25_1h': error_pm25_1h,
                'error_pm25_3h': error_pm25_3h,
                'error_aqi_1h': error_aqi_1h,
                'error_aqi_3h': error_aqi_3h,
                'category_correct_1h': cat_correct_1h,
                'category_correct_3h': cat_correct_3h
            })
        
        results_df = pd.DataFrame(sensor_results)
        all_results.append(results_df)
        
        # Print summary
        print(f"\nResults for Sensor {sensor_id}:")
        print(f"  1-Hour:  MAE={results_df['error_pm25_1h'].abs().mean():.2f} μg/m³, "
              f"Bias={results_df['error_pm25_1h'].mean():.2f}, "
              f"Cat Acc={results_df['category_correct_1h'].mean()*100:.1f}%")
        print(f"  3-Hour:  MAE={results_df['error_pm25_3h'].abs().mean():.2f} μg/m³, "
              f"Bias={results_df['error_pm25_3h'].mean():.2f}, "
              f"Cat Acc={results_df['category_correct_3h'].mean()*100:.1f}%")
    
    # Combine all results
    combined_results = pd.concat(all_results, ignore_index=True)
    
    # Overall summary
    print(f"\n{'='*80}")
    print("Overall Summary (All Sensors)")
    print(f"{'='*80}")
    print(f"Total samples: {len(combined_results):,}")
    print(f"Number of sensors: {len(sensor_ids)}")
    print(f"\n1-Hour Forecast:")
    print(f"  PM2.5 MAE:  {combined_results['error_pm25_1h'].abs().mean():.2f} μg/m³")
    print(f"  PM2.5 RMSE: {np.sqrt((combined_results['error_pm25_1h']**2).mean()):.2f} μg/m³")
    print(f"  PM2.5 Bias: {combined_results['error_pm25_1h'].mean():.2f} μg/m³")
    print(f"  AQI MAE:    {combined_results['error_aqi_1h'].abs().mean():.2f} AQI")
    print(f"  Category Accuracy: {combined_results['category_correct_1h'].mean()*100:.1f}%")
    print(f"\n3-Hour Forecast:")
    print(f"  PM2.5 MAE:  {combined_results['error_pm25_3h'].abs().mean():.2f} μg/m³")
    print(f"  PM2.5 RMSE: {np.sqrt((combined_results['error_pm25_3h']**2).mean()):.2f} μg/m³")
    print(f"  PM2.5 Bias: {combined_results['error_pm25_3h'].mean():.2f} μg/m³")
    print(f"  AQI MAE:    {combined_results['error_aqi_3h'].abs().mean():.2f} AQI")
    print(f"  Category Accuracy: {combined_results['category_correct_3h'].mean()*100:.1f}%")
    
    return combined_results


def plot_sensor_diagnostic(df, sensor_id, output_dir, weeks=2):
    """
    Plot 1-2 weeks of data for a sensor showing actual vs predicted 1h vs 3h.
    """
    sensor_df = df[df['sensor_id'] == int(sensor_id)].copy()
    if 'timestamp' in sensor_df.columns:
        sensor_df = sensor_df.sort_values('timestamp').reset_index(drop=True)
        time_col = 'timestamp'
    elif 'time_stamp' in sensor_df.columns:
        sensor_df = sensor_df.sort_values('time_stamp').reset_index(drop=True)
        time_col = 'time_stamp'
    else:
        print(f"Cannot plot: no timestamp column found")
        return
    
    # Filter to last N weeks
    if len(sensor_df) > 0:
        end_date = sensor_df[time_col].max()
        start_date = end_date - pd.Timedelta(weeks=weeks)
        sensor_df = sensor_df[sensor_df[time_col] >= start_date].copy()
    
    if len(sensor_df) == 0:
        print(f"No data to plot for sensor {sensor_id}")
        return
    
    # Create plot
    fig, axes = plt.subplots(2, 1, figsize=(15, 10))
    
    # Plot 1: 1-hour forecast
    ax1 = axes[0]
    ax1.plot(sensor_df[time_col], sensor_df['actual_pm25_1h'], 
             label='Actual', linewidth=2, alpha=0.7)
    ax1.plot(sensor_df[time_col], sensor_df['pred_pm25_1h'], 
             label='Predicted 1h', linewidth=1.5, alpha=0.8, linestyle='--')
    ax1.set_xlabel('Time')
    ax1.set_ylabel('PM2.5 (μg/m³)')
    ax1.set_title(f'Sensor {sensor_id} - 1-Hour Forecast (Last {weeks} weeks)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: 3-hour forecast
    ax2 = axes[1]
    ax2.plot(sensor_df[time_col], sensor_df['actual_pm25_3h'], 
             label='Actual', linewidth=2, alpha=0.7)
    ax2.plot(sensor_df[time_col], sensor_df['pred_pm25_3h'], 
             label='Predicted 3h', linewidth=1.5, alpha=0.8, linestyle='--')
    ax2.set_xlabel('Time')
    ax2.set_ylabel('PM2.5 (μg/m³)')
    ax2.set_title(f'Sensor {sensor_id} - 3-Hour Forecast (Last {weeks} weeks)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save plot
    output_file = os.path.join(output_dir, f'sensor_{sensor_id}_diagnostic_{weeks}weeks.png')
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Saved diagnostic plot to: {output_file}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description='Validate v2 model using processed dataset')
    parser.add_argument('--processed-file', type=str,
                       default=None,
                       help='Path to processed dataset with features')
    parser.add_argument('--model-dir', type=str,
                       default=None,
                       help='Directory containing v2 models')
    parser.add_argument('--sensor-ids', type=str, nargs='+',
                       default=None,
                       help='Sensor IDs to validate (default: all)')
    parser.add_argument('--num-samples', type=int, default=2000,
                       help='Number of samples per sensor')
    parser.add_argument('--start-date', type=str, default='2025-06-01',
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default='2025-12-31',
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--output', type=str, default=None,
                       help='Output CSV file')
    parser.add_argument('--plot-sensor', type=int, default=None,
                       help='Sensor ID to create diagnostic plot for')
    parser.add_argument('--plot-weeks', type=int, default=2,
                       help='Number of weeks to plot')
    
    args = parser.parse_args()
    
    # Determine paths
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    
    if args.processed_file is None:
        processed_file = project_dir / "data" / "processed" / "dataset_with_features.csv"
    else:
        processed_file = Path(args.processed_file)
    
    if args.model_dir is None:
        model_dir = project_dir / "models" / "v2"
    else:
        model_dir = Path(args.model_dir)
    
    # Run validation
    results_df = validate_from_processed_dataset(
        processed_file, model_dir,
        sensor_ids=args.sensor_ids,
        num_samples_per_sensor=args.num_samples,
        start_date=args.start_date,
        end_date=args.end_date
    )
    
    # Save results
    if args.output:
        output_file = args.output
    else:
        output_file = f"validation_from_processed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    results_df.to_csv(output_file, index=False)
    print(f"\n✓ Results saved to: {output_file}")
    
    # Create diagnostic plot if requested
    if args.plot_sensor:
        output_dir = project_dir / "validation_results"
        output_dir.mkdir(exist_ok=True)
        plot_sensor_diagnostic(results_df, args.plot_sensor, output_dir, weeks=args.plot_weeks)


if __name__ == "__main__":
    main()
