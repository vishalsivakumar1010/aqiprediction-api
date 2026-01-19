#!/usr/bin/env python3
"""
Validation Study Script
Runs AQI forecasts for multiple addresses every hour and compares with actual measurements.

Usage:
    python validation_study.py --addresses "addr1,addr2,..." --hours 12 --interval 60
"""

import os
import sys
import time
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import pickle
from pathlib import Path

# Add the original pipeline to path
original_pipeline_dir = os.path.expanduser("~/Downloads/PAIC Data 2 Months")
if original_pipeline_dir not in sys.path:
    sys.path.insert(0, original_pipeline_dir)

# Import test_predictions functions
# We'll import as needed to avoid circular imports
try:
    from test_predictions import (
        load_models, geocode_address, find_nearest_sensor,
        prepare_test_data_from_csv, prepare_features_for_prediction,
        make_predictions, load_sensor_locations, fetch_current_sensor_data_api,
        fetch_current_wind_data_for_prediction, merge_wind_data_for_prediction,
        WIND_FETCHING_AVAILABLE
    )
except ImportError:
    # If imports fail, we'll import dynamically
    pass

from aqi_utils import pm25_to_aqi, aqi_to_category

import requests


class ValidationStudy:
    def __init__(self, addresses, api_key, data_dir, model_dir, hours=12, interval_minutes=60):
        """
        Initialize validation study.
        
        Args:
            addresses: List of addresses to monitor
            api_key: PurpleAir API key
            data_dir: Directory with historical CSV data
            model_dir: Directory with trained models
            hours: Number of hours to run the study
            interval_minutes: Minutes between forecasts (default 60 for hourly)
        """
        self.addresses = addresses
        self.api_key = api_key
        self.data_dir = data_dir
        self.model_dir = model_dir
        self.hours = hours
        self.interval_seconds = interval_minutes * 60
        
        # Load models once at startup
        print("Loading models...")
        self.models = load_models(model_dir)
        print(f"✓ Models loaded: {len(self.models)} horizons")
        
        # Results storage
        self.predictions = []  # List of dicts with predictions
        self.actuals = []  # List of dicts with actual measurements
        
        # Geocode addresses and find sensors once
        self.address_info = {}
        print("\nGeocoding addresses and finding nearest sensors...")
        
        # Load sensor locations once
        try:
            locations_df = load_sensor_locations(data_dir)
            if locations_df is None or locations_df.empty:
                print("  ⚠ Warning: Could not load sensor locations")
                locations_df = None
        except Exception as e:
            print(f"  ⚠ Warning: Could not load sensor locations: {e}")
            locations_df = None
        
        for addr in addresses:
            try:
                lat, lon = geocode_address(addr)
                if locations_df is None:
                    raise ValueError("Sensor locations not available")
                
                # Call find_nearest_sensor - it returns {'nearest': {...}, 'top_3': [...]}
                sensor_info = find_nearest_sensor(lat, lon, locations_df)
                nearest = sensor_info['nearest']  # Extract the nearest sensor dict
                
                self.address_info[addr] = {
                    'coordinates': (lat, lon),
                    'sensor_id': nearest['sensor_id'],
                    'sensor_name': nearest.get('name', 'Unknown'),
                    'distance_km': nearest['distance_km']
                }
                print(f"  ✓ {addr}: Sensor {nearest['sensor_id']} ({nearest.get('name', 'Unknown')}) - {nearest['distance_km']:.2f} km")
            except Exception as e:
                print(f"  ✗ {addr}: Error - {e}")
                import traceback
                traceback.print_exc()
                self.address_info[addr] = None
    
    def fetch_current_measurement(self, sensor_id):
        """Fetch current PM2.5 measurement from PurpleAir API."""
        try:
            url = f"https://api.purpleair.com/v1/sensors/{sensor_id}"
            params = {
                'fields': 'pm2.5_atm,humidity,temperature,last_seen',
                'api_key': self.api_key
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'sensor' in data and len(data['sensor']) > 0:
                sensor_data = data['sensor'][0]
                pm25 = sensor_data.get('pm2.5_atm', None)
                if pm25 is not None:
                    return {
                        'pm25_ugm3': float(pm25),
                        'aqi': pm25_to_aqi(float(pm25)),
                        'category': aqi_to_category(pm25_to_aqi(float(pm25))),
                        'humidity': sensor_data.get('humidity'),
                        'temperature': sensor_data.get('temperature'),
                        'timestamp': datetime.utcnow(),
                        'last_seen': sensor_data.get('last_seen')
                    }
        except Exception as e:
            print(f"    ⚠ Error fetching current measurement: {e}")
        return None
    
    def run_forecast_round(self, round_num, start_time):
        """Run one round of forecasts for all addresses."""
        print(f"\n{'='*70}")
        print(f"ROUND {round_num}/{self.hours} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        
        for addr in self.addresses:
            if self.address_info[addr] is None:
                continue
            
            info = self.address_info[addr]
            sensor_id = info['sensor_id']
            
            print(f"\n{addr}")
            print(f"  Sensor: {info['sensor_name']} (ID: {sensor_id})")
            
            try:
                # Use the same approach as test_predictions.py main function
                # Fetch current live data from API
                try:
                    from test_predictions import fetch_current_sensor_data_api
                except ImportError:
                    fetch_current_sensor_data_api = None
                
                if fetch_current_sensor_data_api is None:
                    # Fallback: use fetch_current_measurement
                    current_data = self.fetch_current_measurement(sensor_id)
                    if current_data is None:
                        print(f"  ✗ Could not fetch current data")
                        continue
                    # Create a minimal dataframe for current data
                    current_df = pd.DataFrame([{
                        'sensor_id': sensor_id,
                        'time_stamp': datetime.utcnow(),
                        'pm2_5_atm': current_data['pm25_ugm3'],
                        'humidity': current_data.get('humidity', 50),
                        'temperature': current_data.get('temperature', 70)
                    }])
                else:
                    current_df = fetch_current_sensor_data_api(self.api_key, sensor_id)
                if current_df is None or len(current_df) == 0:
                    print(f"  ✗ Could not fetch current data")
                    continue
                
                current_row = current_df.iloc[0]
                current_pm25 = current_row['pm2_5_atm']
                current_aqi = pm25_to_aqi(current_pm25)
                current_category = aqi_to_category(current_aqi)
                
                print(f"  Current: PM2.5={current_pm25:.2f}, AQI={int(current_aqi)} ({current_category})")
                
                # Load historical data and combine with current
                try:
                    hist_df = prepare_test_data_from_csv(self.data_dir, sensor_id, num_rows=47)
                    
                    # Convert to UTC-aware, then combine
                    current_df['time_stamp'] = pd.to_datetime(current_df['time_stamp'], utc=True)
                    if hist_df is not None and len(hist_df) > 0:
                        hist_df['time_stamp'] = pd.to_datetime(hist_df['time_stamp'], utc=True)
                        test_df = pd.concat([hist_df, current_df], ignore_index=True).sort_values('time_stamp').reset_index(drop=True)
                    else:
                        test_df = current_df.copy()
                    
                    # Fetch wind data for combined dataset
                    from test_predictions import fetch_current_wind_data_for_prediction, merge_wind_data_for_prediction, WIND_FETCHING_AVAILABLE
                    
                    if WIND_FETCHING_AVAILABLE and 'latitude' in test_df.columns and test_df['latitude'].notna().any():
                        sensor_lat = test_df['latitude'].iloc[0]
                        sensor_lon = test_df['longitude'].iloc[0]
                        wind_data = fetch_current_wind_data_for_prediction(test_df, sensor_lat, sensor_lon)
                        if wind_data is not None:
                            test_df = merge_wind_data_for_prediction(test_df, wind_data)
                
                except Exception as e:
                    print(f"    ⚠ Warning preparing historical data: {e}")
                    test_df = current_df.copy()
                    
                    # Try to get location and wind data
                    from test_predictions import load_sensor_locations, fetch_current_wind_data_for_prediction, merge_wind_data_for_prediction, WIND_FETCHING_AVAILABLE
                    
                    if 'latitude' not in test_df.columns or test_df['latitude'].isna().all():
                        locations_df = load_sensor_locations(self.data_dir)
                        if locations_df is not None:
                            sensor_locs = locations_df[locations_df['sensor_id'] == int(sensor_id)]
                            if not sensor_locs.empty:
                                test_df['latitude'] = sensor_locs.iloc[0]['latitude']
                                test_df['longitude'] = sensor_locs.iloc[0]['longitude']
                    
                    if WIND_FETCHING_AVAILABLE and 'latitude' in test_df.columns and test_df['latitude'].notna().any():
                        sensor_lat = test_df['latitude'].iloc[0]
                        sensor_lon = test_df['longitude'].iloc[0]
                        wind_data = fetch_current_wind_data_for_prediction(test_df, sensor_lat, sensor_lon)
                        if wind_data is not None:
                            test_df = merge_wind_data_for_prediction(test_df, wind_data)
                
                # Prepare features
                feature_row = prepare_features_for_prediction(test_df, sensor_id)
                feature_columns = self.models['1h']['feature_columns']
                
                # Reorder features to match model order (as done in test_predictions.py)
                feature_row_reordered = pd.DataFrame()
                for col in feature_columns:
                    if col in feature_row.columns:
                        feature_row_reordered[col] = [feature_row[col].iloc[0]]
                    else:
                        feature_row_reordered[col] = [np.nan]
                feature_row = feature_row_reordered
                
                # Make predictions with ensemble (60% ML + 40% persistence)
                predictions = make_predictions(self.models, feature_row, feature_columns, current_pm25=current_pm25, ensemble_weight=0.6)
                
                # Store results (use current_row, not current_data)
                result = {
                    'round': round_num,
                    'timestamp': datetime.now(),
                    'address': addr,
                    'sensor_id': sensor_id,
                    'sensor_name': info['sensor_name'],
                    'current_pm25': current_pm25,
                    'current_aqi': int(current_aqi),
                    'current_category': current_category,
                    'forecast_1h_pm25': predictions['1h']['pm25_ugm3'],
                    'forecast_1h_aqi': predictions['1h']['aqi'],
                    'forecast_1h_category': predictions['1h']['category'],
                    'forecast_3h_pm25': predictions['3h']['pm25_ugm3'],
                    'forecast_3h_aqi': predictions['3h']['aqi'],
                    'forecast_3h_category': predictions['3h']['category'],
                }
                self.predictions.append(result)
                
                print(f"  1h Forecast: PM2.5={result['forecast_1h_pm25']:.2f}, AQI={result['forecast_1h_aqi']} ({result['forecast_1h_category']})")
                print(f"  3h Forecast: PM2.5={result['forecast_3h_pm25']:.2f}, AQI={result['forecast_3h_aqi']} ({result['forecast_3h_category']})")
                
            except Exception as e:
                print(f"  ✗ Error: {e}")
                import traceback
                traceback.print_exc()
        
        # Save results incrementally
        self.save_results()
    
    def fetch_actuals_for_comparison(self):
        """Fetch actual measurements to compare with past predictions."""
        print(f"\n{'='*70}")
        print("FETCHING ACTUAL MEASUREMENTS FOR COMPARISON")
        print(f"{'='*70}")
        
        # Group predictions by (address, round, forecast_horizon)
        # For each prediction, fetch the actual value at the forecast time
        
        for pred in self.predictions:
            # Calculate when the actual measurement should be taken
            # 1h forecast: actual should be at timestamp + 1 hour
            # 3h forecast: actual should be at timestamp + 3 hours
            
            for horizon in ['1h', '3h']:
                forecast_time = pred['timestamp'] + timedelta(hours=int(horizon[0]))
                hours_ahead = int(horizon[0])
                
                # Only fetch if enough time has passed
                if datetime.now() < forecast_time:
                    continue  # Too early, actual not available yet
                
                addr = pred['address']
                if self.address_info[addr] is None:
                    continue
                
                sensor_id = self.address_info[addr]['sensor_id']
                
                try:
                    # Fetch actual measurement (use API or historical data)
                    # For now, we'll fetch current and compare if close enough
                    # In a real scenario, you'd want to fetch historical data at the exact forecast time
                    actual = self.fetch_current_measurement(sensor_id)
                    
                    if actual:
                        actual_result = {
                            'prediction_timestamp': pred['timestamp'],
                            'forecast_time': forecast_time,
                            'address': addr,
                            'sensor_id': sensor_id,
                            'horizon': horizon,
                            'forecast_pm25': pred[f'forecast_{horizon}_pm25'],
                            'forecast_aqi': pred[f'forecast_{horizon}_aqi'],
                            'actual_pm25': actual['pm25_ugm3'],
                            'actual_aqi': actual['aqi'],
                            'actual_category': actual['category'],
                            'measurement_timestamp': actual['timestamp'],
                            'error_pm25': abs(actual['pm25_ugm3'] - pred[f'forecast_{horizon}_pm25']),
                            'error_aqi': abs(actual['aqi'] - pred[f'forecast_{horizon}_aqi']),
                        }
                        self.actuals.append(actual_result)
                        
                except Exception as e:
                    print(f"  ⚠ Error fetching actual for {addr} {horizon}: {e}")
    
    def save_results(self):
        """Save results to files."""
        import sys
        output_dir = Path(self.data_dir) / 'validation_results'
        output_dir.mkdir(exist_ok=True)
        
        # Use a fixed timestamp based on study start (first prediction) to avoid overwriting
        if self.predictions:
            study_start = min(p['timestamp'] for p in self.predictions)
            timestamp = study_start.strftime('%Y%m%d_%H%M%S')
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save predictions (append mode for incremental saves)
        if self.predictions:
            pred_df = pd.DataFrame(self.predictions)
            pred_file = output_dir / f'predictions_{timestamp}.csv'
            pred_df.to_csv(pred_file, index=False)
            print(f"\n✓ Saved {len(self.predictions)} predictions to {pred_file}")
            sys.stdout.flush()
        
        # Save actuals/comparisons
        if self.actuals:
            actual_df = pd.DataFrame(self.actuals)
            actual_file = output_dir / f'actuals_comparison_{timestamp}.csv'
            actual_df.to_csv(actual_file, index=False)
            print(f"✓ Saved {len(self.actuals)} actual comparisons to {actual_file}")
            sys.stdout.flush()
        
        # Save summary JSON (update with latest info)
        summary = {
            'study_start': self.predictions[0]['timestamp'].isoformat() if self.predictions else None,
            'addresses': self.addresses,
            'total_rounds': len(set(p['round'] for p in self.predictions)) if self.predictions else 0,
            'total_predictions': len(self.predictions),
            'total_comparisons': len(self.actuals),
            'address_info': {k: str(v) for k, v in self.address_info.items()} if self.address_info else {}
        }
        summary_file = output_dir / f'summary_{timestamp}.json'
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"✓ Updated summary: {summary_file}")
        sys.stdout.flush()
    
    def generate_report(self):
        """Generate a comparison report."""
        if not self.actuals:
            print("\n⚠ No actual measurements available for comparison yet.")
            print("  Run fetch_actuals_for_comparison() after enough time has passed.")
            return
        
        print(f"\n{'='*70}")
        print("VALIDATION STUDY REPORT")
        print(f"{'='*70}")
        
        df = pd.DataFrame(self.actuals)
        
        print(f"\nTotal Comparisons: {len(df)}")
        print(f"  - 1h forecasts: {len(df[df['horizon'] == '1h'])}")
        print(f"  - 3h forecasts: {len(df[df['horizon'] == '3h'])}")
        
        print(f"\nError Statistics (PM2.5):")
        print(f"  Mean Absolute Error (MAE): {df['error_pm25'].mean():.2f} μg/m³")
        print(f"  Root Mean Squared Error (RMSE): {np.sqrt((df['error_pm25']**2).mean()):.2f} μg/m³")
        print(f"  Median Error: {df['error_pm25'].median():.2f} μg/m³")
        print(f"  Max Error: {df['error_pm25'].max():.2f} μg/m³")
        
        print(f"\nError Statistics (AQI):")
        print(f"  Mean Absolute Error (MAE): {df['error_aqi'].mean():.2f}")
        print(f"  Root Mean Squared Error (RMSE): {np.sqrt((df['error_aqi']**2).mean()):.2f}")
        print(f"  Median Error: {df['error_aqi'].median():.2f}")
        
        print(f"\nBy Forecast Horizon:")
        for horizon in ['1h', '3h']:
            h_df = df[df['horizon'] == horizon]
            if len(h_df) > 0:
                print(f"\n  {horizon.upper()} Forecast:")
                print(f"    MAE (PM2.5): {h_df['error_pm25'].mean():.2f} μg/m³")
                print(f"    MAE (AQI): {h_df['error_aqi'].mean():.2f}")
                print(f"    RMSE (PM2.5): {np.sqrt((h_df['error_pm25']**2).mean()):.2f} μg/m³")
        
        print(f"\nBy Address:")
        for addr in df['address'].unique():
            addr_df = df[df['address'] == addr]
            print(f"\n  {addr}:")
            print(f"    Comparisons: {len(addr_df)}")
            print(f"    MAE (PM2.5): {addr_df['error_pm25'].mean():.2f} μg/m³")
            print(f"    MAE (AQI): {addr_df['error_aqi'].mean():.2f}")
        
        # Save detailed report
        output_dir = Path(self.data_dir) / 'validation_results'
        output_dir.mkdir(exist_ok=True)
        report_file = output_dir / f'report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        with open(report_file, 'w') as f:
            f.write("VALIDATION STUDY REPORT\n")
            f.write("="*70 + "\n")
            f.write(f"Generated: {datetime.now()}\n\n")
            f.write(df.to_string())
        print(f"\n✓ Detailed report saved to {report_file}")
    
    def run(self):
        """Run the complete validation study."""
        import sys
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=self.hours)
        
        print(f"\n{'='*70}")
        print("VALIDATION STUDY STARTING")
        print(f"{'='*70}")
        print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Duration: {self.hours} hours")
        print(f"Interval: {self.interval_seconds / 60:.0f} minutes")
        print(f"Addresses: {len(self.addresses)}")
        print(f"{'='*70}")
        sys.stdout.flush()  # Ensure output is flushed
        
        # Round 1: Run immediately
        print(f"\n>>> Running Round 1 immediately...")
        sys.stdout.flush()
        self.run_forecast_round(1, start_time)
        sys.stdout.flush()
        
        # Rounds 2-12: Run at hourly intervals
        for round_num in range(2, self.hours + 1):
            # Check if we should continue
            if datetime.now() >= end_time:
                break
            
            # Calculate when next round should start (1 hour after start time for round 2, 2 hours for round 3, etc.)
            next_round_time = start_time + timedelta(seconds=self.interval_seconds * (round_num - 1))
            wait_seconds = (next_round_time - datetime.now()).total_seconds()
            
            if wait_seconds > 0:
                print(f"\n>>> Waiting {wait_seconds/60:.1f} minutes until Round {round_num}...")
                sys.stdout.flush()
                time.sleep(wait_seconds)
            
            print(f"\n>>> Running Round {round_num}...")
            sys.stdout.flush()
            self.run_forecast_round(round_num, start_time)
            sys.stdout.flush()
        
        print(f"\n{'='*70}")
        print("VALIDATION STUDY COMPLETE")
        print(f"{'='*70}")
        
        # Try to fetch actuals for comparison
        print("\nAttempting to fetch actual measurements for comparison...")
        self.fetch_actuals_for_comparison()
        
        # Generate report
        self.generate_report()
        
        print(f"\n✓ Validation study complete!")
        print(f"  Total predictions: {len(self.predictions)}")
        print(f"  Total comparisons: {len(self.actuals)}")


def main():
    import sys
    parser = argparse.ArgumentParser(description='Run AQI forecast validation study')
    parser.add_argument('--addresses', default=None, help='Comma or semicolon-separated list of addresses (or use --address-file)')
    parser.add_argument('--address-file', default=None, help='File with one address per line (recommended)')
    parser.add_argument('--api-key', required=True, help='PurpleAir API key')
    parser.add_argument('--hours', type=int, default=12, help='Number of hours to run (default: 12)')
    parser.add_argument('--interval', type=int, default=60, help='Minutes between forecasts (default: 60)')
    parser.add_argument('--data-dir', default=None, help='Data directory with CSVs (default: script location)')
    parser.add_argument('--model-dir', default=None, help='Model directory (default: script location/models)')
    
    args = parser.parse_args()
    
    # Parse addresses - prefer file, fallback to argument
    import re
    
    if args.address_file:
        # Read from file (one address per line)
        address_file = Path(args.address_file)
        if not address_file.exists():
            # Try relative to script directory
            script_dir = Path(__file__).parent
            address_file = script_dir / args.address_file
        
        if address_file.exists():
            with open(address_file, 'r') as f:
                addresses = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            print(f"Loaded {len(addresses)} addresses from {address_file}")
        else:
            print(f"ERROR: Address file not found: {args.address_file}")
            sys.exit(1)
    elif args.addresses:
        # Try semicolon separator first (more reliable for addresses with commas)
        if ';' in args.addresses:
            addresses = [addr.strip() for addr in args.addresses.split(';') if addr.strip()]
        else:
            # Parse comma-separated by grouping until we hit a ZIP code
            parts = [p.strip() for p in args.addresses.split(',')]
            addresses = []
            current_addr = []
            
            for part in parts:
                current_addr.append(part)
                # If this part has a ZIP code (5 digits), we have a complete address
                if re.search(r'\d{5}', part):
                    addresses.append(', '.join(current_addr))
                    current_addr = []
            
            # Add any remaining parts as a final address
            if current_addr:
                addresses.append(', '.join(current_addr))
        
        # Filter out incomplete addresses
        addresses = [a for a in addresses if len(a) > 10 and not re.match(r'^(Fremont|CA|\d{5})$', a.strip())]
        print(f"Parsed {len(addresses)} addresses from command line")
    else:
        # Try default file
        script_dir = Path(__file__).parent
        default_file = script_dir / 'validation_addresses_list.txt'
        if default_file.exists():
            with open(default_file, 'r') as f:
                addresses = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            print(f"Loaded {len(addresses)} addresses from default file: {default_file}")
        else:
            print("ERROR: No addresses provided. Use --addresses or --address-file")
            sys.exit(1)
    
    if len(addresses) == 0:
        print("ERROR: No valid addresses found. Please check address format.")
        sys.exit(1)
    
    print(f"Using {len(addresses)} addresses for validation study")
    
    # Set default directories
    if args.data_dir is None:
        args.data_dir = os.path.dirname(os.path.abspath(__file__))
    if args.model_dir is None:
        args.model_dir = os.path.join(args.data_dir, 'models')
    
    # Run validation study
    study = ValidationStudy(
        addresses=addresses,
        api_key=args.api_key,
        data_dir=args.data_dir,
        model_dir=args.model_dir,
        hours=args.hours,
        interval_minutes=args.interval
    )
    
    study.run()


if __name__ == '__main__':
    main()
