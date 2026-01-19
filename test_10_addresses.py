"""
Test model against 10 validation addresses.

This script:
1. Loads the trained models
2. Tests predictions for each of the 10 validation addresses
3. Fetches current live data from PurpleAir API
4. Makes predictions with the ensemble approach
5. Prints detailed results
"""

import sys
import os
import pandas as pd
from datetime import datetime
import warnings

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
        load_models, geocode_address, find_nearest_sensor,
        prepare_features_for_prediction, make_predictions,
        load_sensor_locations, fetch_current_sensor_data_api,
        fetch_current_wind_data_for_prediction, merge_wind_data_for_prediction,
        WIND_FETCHING_AVAILABLE
    )
    from aqi_utils import pm25_to_aqi, aqi_to_category
except ImportError as e:
    print(f"Error: Could not import required modules: {e}")
    sys.exit(1)


def test_address(address, api_key, model_dir, data_dir):
    """
    Test prediction for a single address.
    
    Returns:
        Dictionary with results or None if failed
    """
    try:
        # Geocode address
        lat, lon = geocode_address(address)
        if lat is None or lon is None:
            print(f"  ✗ Could not geocode address")
            return None
        
        # Load sensor locations
        locations_df = load_sensor_locations(data_dir)
        if locations_df is None or locations_df.empty:
            print(f"  ✗ Could not load sensor locations")
            return None
        
        # Find nearest sensor
        sensor_info_dict = find_nearest_sensor(lat, lon, locations_df)
        nearest_sensor = sensor_info_dict['nearest']
        sensor_id = nearest_sensor['sensor_id']
        sensor_name = nearest_sensor['name']
        distance_km = nearest_sensor['distance_km']
        
        # Fetch current live data
        current_df = fetch_current_sensor_data_api(api_key, sensor_id)
        current_pm25 = current_df['pm2_5_atm'].iloc[0]
        current_aqi = pm25_to_aqi(current_pm25)
        current_category = aqi_to_category(current_aqi)
        
        # Load historical data for features
        from test_predictions import prepare_test_data_from_csv
        try:
            hist_df = prepare_test_data_from_csv(data_dir, sensor_id, num_rows=47)
            
            # Combine historical + current
            current_df['time_stamp'] = pd.to_datetime(current_df['time_stamp'], utc=True)
            hist_df['time_stamp'] = pd.to_datetime(hist_df['time_stamp'], utc=True)
            test_df = pd.concat([hist_df, current_df], ignore_index=True)
            test_df = test_df.sort_values('time_stamp').reset_index(drop=True)
            
            # Fetch wind data
            if WIND_FETCHING_AVAILABLE and 'latitude' in test_df.columns and test_df['latitude'].notna().any():
                sensor_lat = test_df['latitude'].iloc[0]
                sensor_lon = test_df['longitude'].iloc[0]
                wind_data = fetch_current_wind_data_for_prediction(test_df, sensor_lat, sensor_lon)
                if wind_data is not None:
                    test_df = merge_wind_data_for_prediction(test_df, wind_data)
        except Exception as e:
            print(f"  ⚠ Warning: Could not load historical data: {e}")
            # Use just current data (limited features)
            test_df = current_df.copy()
        
        # Prepare features
        feature_row = prepare_features_for_prediction(test_df, sensor_id)
        models = load_models(model_dir)
        feature_columns = models['1h']['feature_columns']
        
        # Make predictions with ensemble
        predictions = make_predictions(models, feature_row, feature_columns, 
                                       current_pm25=current_pm25, ensemble_weight=0.6)
        
        return {
            'address': address,
            'sensor_id': sensor_id,
            'sensor_name': sensor_name,
            'distance_km': distance_km,
            'current_pm25': current_pm25,
            'current_aqi': current_aqi,
            'current_category': current_category,
            'pred_1h_pm25': predictions['1h']['pm25_ugm3'],
            'pred_1h_aqi': predictions['1h']['aqi'],
            'pred_1h_category': predictions['1h']['category'],
            'pred_3h_pm25': predictions['3h']['pm25_ugm3'],
            'pred_3h_aqi': predictions['3h']['aqi'],
            'pred_3h_category': predictions['3h']['category'],
            'success': True
        }
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return {
            'address': address,
            'success': False,
            'error': str(e)
        }


def main():
    # Configuration
    API_KEY = "C258449D-E52B-11F0-B596-4201AC1DC123"
    MODEL_DIR = "models"
    DATA_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # 10 validation addresses
    addresses = [
        '2523 Bishop Ave, Fremont, CA 94536',
        '39400 Paseo Padre Pkwy, Fremont, CA 94538',
        '4620 Mattos Dr, Fremont, CA 94536',
        '5400 Mowry Ave, Fremont, CA 94538',
        '36007 Pizarro Dr, Fremont, CA 94536',
        '3377 Alder Ave, Fremont, CA 94536',
        '34665 Allegheny Ct, Fremont, CA 94555',
        '1251 Peralta Blvd, Fremont, CA 94536',
        '40500 Paseo Padre Pkwy, Fremont, CA 94538',
        '41800 Blacow Rd, Fremont, CA 94538'
    ]
    
    print("="*100)
    print("MODEL VALIDATION - 10 ADDRESSES")
    print("="*100)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Model directory: {MODEL_DIR}")
    print(f"Data directory: {DATA_DIR}")
    print(f"API Key: {API_KEY[:20]}...")
    print()
    
    # Load models
    print("Loading models...")
    try:
        models = load_models(MODEL_DIR)
        print(f"✓ Models loaded successfully")
        print(f"  - 1h forecast model: {len(models['1h']['feature_columns'])} features")
        print(f"  - 3h forecast model: {len(models['3h']['feature_columns'])} features")
    except Exception as e:
        print(f"✗ Error loading models: {e}")
        sys.exit(1)
    
    print()
    print("="*100)
    print("TESTING ADDRESSES")
    print("="*100)
    print()
    
    results = []
    
    for i, address in enumerate(addresses, 1):
        print(f"[{i}/10] {address}")
        print("-" * 100)
        result = test_address(address, API_KEY, MODEL_DIR, DATA_DIR)
        
        if result and result.get('success'):
            results.append(result)
            
            print(f"  Sensor: {result['sensor_name']} (ID: {result['sensor_id']}, {result['distance_km']:.2f} km)")
            print(f"  Current: PM2.5 {result['current_pm25']:.1f} μg/m³, AQI {result['current_aqi']} ({result['current_category']})")
            print(f"  1h Forecast: PM2.5 {result['pred_1h_pm25']:.1f} μg/m³, AQI {result['pred_1h_aqi']} ({result['pred_1h_category']})")
            print(f"  3h Forecast: PM2.5 {result['pred_3h_pm25']:.1f} μg/m³, AQI {result['pred_3h_aqi']} ({result['pred_3h_category']})")
            print()
        else:
            results.append(result)
            print()
    
    # Summary
    print()
    print("="*100)
    print("SUMMARY")
    print("="*100)
    print()
    
    successful = sum(1 for r in results if r and r.get('success'))
    print(f"Successful predictions: {successful}/10")
    print()
    
    if successful > 0:
        # Create summary table
        print("Detailed Results:")
        print("-" * 100)
        print(f"{'Address':<40} {'Current':<15} {'1h Forecast':<20} {'3h Forecast':<20}")
        print("-" * 100)
        
        for r in results:
            if r and r.get('success'):
                addr_short = r['address'].split(',')[0][:38] if ',' in r['address'] else r['address'][:38]
                current_str = f"AQI {r['current_aqi']} ({r['current_category']})"
                pred_1h_str = f"AQI {r['pred_1h_aqi']} ({r['pred_1h_category']})"
                pred_3h_str = f"AQI {r['pred_3h_aqi']} ({r['pred_3h_category']})"
                print(f"{addr_short:<40} {current_str:<15} {pred_1h_str:<20} {pred_3h_str:<20}")
        
        print("-" * 100)
        print()
        
        # Statistics
        current_aqis = [r['current_aqi'] for r in results if r and r.get('success')]
        pred_1h_aqis = [r['pred_1h_aqi'] for r in results if r and r.get('success')]
        pred_3h_aqis = [r['pred_3h_aqi'] for r in results if r and r.get('success')]
        
        print("Statistics:")
        print(f"  Current AQI:   Min {min(current_aqis):3d}, Max {max(current_aqis):3d}, Avg {sum(current_aqis)/len(current_aqis):.1f}")
        print(f"  1h Forecast:   Min {min(pred_1h_aqis):3d}, Max {max(pred_1h_aqis):3d}, Avg {sum(pred_1h_aqis)/len(pred_1h_aqis):.1f}")
        print(f"  3h Forecast:   Min {min(pred_3h_aqis):3d}, Max {max(pred_3h_aqis):3d}, Avg {sum(pred_3h_aqis)/len(pred_3h_aqis):.1f}")
        print()
        
        # Category distribution
        print("Category Distribution:")
        from collections import Counter
        current_cats = Counter([r['current_category'] for r in results if r and r.get('success')])
        pred_1h_cats = Counter([r['pred_1h_category'] for r in results if r and r.get('success')])
        pred_3h_cats = Counter([r['pred_3h_category'] for r in results if r and r.get('success')])
        
        print(f"  Current:   {dict(current_cats)}")
        print(f"  1h Forecast: {dict(pred_1h_cats)}")
        print(f"  3h Forecast: {dict(pred_3h_cats)}")
        print()
        
        # Save results to CSV
        results_df = pd.DataFrame([r for r in results if r and r.get('success')])
        output_file = f"validation_10_addresses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        results_df.to_csv(output_file, index=False)
        print(f"✓ Results saved to: {output_file}")
    else:
        print("✗ No successful predictions")
    
    print()
    print("="*100)
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*100)
    
    return results


if __name__ == "__main__":
    main()
