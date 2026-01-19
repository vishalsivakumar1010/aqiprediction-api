"""
Complete Training Pipeline for Full 2025 Dataset
1. Loads PurpleAir data
2. Fetches historical wind direction from Meteostat (matching exact timestamps)
3. Merges wind direction
4. Adds sensor locations
5. Engineers features
6. Trains models
"""

import os
import sys
from datetime import datetime

# Add the original pipeline directory to path if needed
original_pipeline_dir = os.path.expanduser("~/Downloads/PAIC Data 2 Months")
if os.path.exists(original_pipeline_dir):
    sys.path.insert(0, original_pipeline_dir)

try:
    from aqi_utils import add_aqi_to_dataframe
    from feature_engineering import engineer_features
    from model_training import train_all_models
except ImportError:
    print("Warning: Original pipeline modules not found. Using inline versions.")
    # We'll need to import or define these functions

# Import our new preparation script
from prepare_full_dataset import prepare_full_dataset, load_sensor_locations


def main():
    """
    Main training pipeline for full 2025 dataset
    """
    print("="*80)
    print("AQI PREDICTION MODEL TRAINING - FULL 2025 DATASET")
    print("="*80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Get data directory (current directory where script is run)
    data_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Step 1: Prepare complete dataset with historical wind direction
    print("STEP 1: Preparing complete dataset with historical wind direction")
    print("="*80)
    try:
        df = prepare_full_dataset(
            data_dir, 
            latitude=37.5483,  # Fremont, CA center
            longitude=-121.9886  # Fremont, CA center
        )
        
        # Save prepared dataset
        output_file = os.path.join(data_dir, 'purpleair_complete_with_wind.csv')
        print(f"\nSaving prepared dataset to: {output_file}")
        df.to_csv(output_file, index=False)
        print(f"Saved {len(df)} rows\n")
        
    except Exception as e:
        print(f"Error preparing dataset: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Step 2: Add AQI calculations
    print("\nSTEP 2: Calculating AQI values")
    print("="*80)
    try:
        from aqi_utils import add_aqi_to_dataframe
        df = add_aqi_to_dataframe(df)
        print(f"Added AQI values. AQI range: {df['aqi'].min()} - {df['aqi'].max()}")
    except Exception as e:
        print(f"Error calculating AQI: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Step 3: Feature engineering
    print("\nSTEP 3: Engineering features")
    print("="*80)
    try:
        # Check if location data is available
        has_locations = 'latitude' in df.columns and df['latitude'].notna().any()
        if has_locations:
            print(f"Location data found. Including spatial features.")
        else:
            print("No location data found. Spatial features will be skipped.")
        
        # Check if wind direction is available
        has_wind = 'wdir' in df.columns and df['wdir'].notna().any()
        if has_wind:
            wind_coverage = df['wdir'].notna().sum() / len(df) * 100
            print(f"Wind direction data found. Coverage: {wind_coverage:.1f}%")
        else:
            print("Warning: No wind direction data found!")
        
        # Engineer features (includes temporal, lagged, rolling, spatial, and wind features)
        df_features = engineer_features(
            df, 
            include_targets=True, 
            include_spatial_features=has_locations
        )
        
        print(f"\nFeature engineering complete. Created {df_features.shape[1]} features.")
        
        # Show feature count breakdown
        feature_types = {
            'Time features': [c for c in df_features.columns if any(x in c for x in ['hour', 'day', 'month', '_sin', '_cos', 'is_weekend', 'is_rush'])],
            'Lag features': [c for c in df_features.columns if '_lag_' in c],
            'Rolling features': [c for c in df_features.columns if 'rolling_' in c],
            'Spatial features': [c for c in df_features.columns if any(x in c for x in ['latitude', 'longitude', 'distance', 'nearby'])],
            'Wind features': [c for c in df_features.columns if any(x in c for x in ['wind_dir', 'wdir'])],
            'Original features': ['pm2_5_atm', 'humidity', 'temperature']
        }
        print(f"\nFeature breakdown:")
        for ftype, feats in feature_types.items():
            actual_feats = [f for f in feats if f in df_features.columns]
            if actual_feats:
                print(f"  {ftype}: {len(actual_feats)}")
        
    except Exception as e:
        print(f"Error in feature engineering: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Step 4: Train models
    print("\nSTEP 4: Training models")
    print("="*80)
    model_dir = os.path.join(data_dir, 'models')
    os.makedirs(model_dir, exist_ok=True)
    
    try:
        results = train_all_models(df_features, model_dir=model_dir)
        
        print("\n" + "="*80)
        print("TRAINING COMPLETE!")
        print("="*80)
        print(f"\nFinished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\nModels saved to: {model_dir}/")
        print("\nModel Performance Summary:")
        print("-"*80)
        print(f"\n1-Hour Forecast Performance:")
        print(f"  PM2.5 MAE: {results['1h']['pm25_metrics']['mae']:.2f} μg/m³")
        print(f"  PM2.5 R²: {results['1h']['pm25_metrics']['r2']:.4f}")
        print(f"  Category Accuracy: {results['1h']['category_metrics']['accuracy']:.4f}")
        print(f"\n3-Hour Forecast Performance:")
        print(f"  PM2.5 MAE: {results['3h']['pm25_metrics']['mae']:.2f} μg/m³")
        print(f"  PM2.5 R²: {results['3h']['pm25_metrics']['r2']:.4f}")
        print(f"  Category Accuracy: {results['3h']['category_metrics']['accuracy']:.4f}")
        
        print("\n" + "="*80)
        print("You can now use these models to make predictions:")
        print("  python predict.py <API_KEY> <SENSOR_ID>")
        print("="*80)
        
    except Exception as e:
        print(f"Error training models: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

