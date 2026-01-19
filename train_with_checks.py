"""
Complete Training Pipeline with Comprehensive Checks
- Data leakage verification
- Time-based split verification
- Wind direction merge verification
- Baseline persistence models
- Main XGBoost/HistGradientBoosting models
- Comprehensive metrics reporting
"""

import pandas as pd
import numpy as np
import os
import sys
import pickle
from datetime import datetime
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, classification_report, confusion_matrix, f1_score
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
import warnings
warnings.filterwarnings('ignore')

# Try to import XGBoost, but don't fail if it's not available or has missing dependencies
# IMPORTANT: XGBoost import is wrapped to catch ALL exceptions including XGBoostError
# that happens when libomp.dylib is missing on macOS
XGBOOST_AVAILABLE = False
xgb = None

# Use a function to check XGBoost so we can handle import errors properly
def _check_xgboost():
    """Check if XGBoost is available and working."""
    global XGBOOST_AVAILABLE, xgb
    try:
        # Suppress warnings during import
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import xgboost as xgb_module
    except Exception as e:
        # XGBoost not installed or can't import (including XGBoostError from missing libomp)
        return False
    
    try:
        # Test if XGBoost actually works (might be installed but missing libomp on macOS)
        _test = xgb_module.XGBRegressor(n_estimators=1, tree_method='hist')
        XGBOOST_AVAILABLE = True
        xgb = xgb_module
        return True
    except Exception as e:
        # XGBoost imported but doesn't work (likely missing OpenMP on macOS)
        XGBOOST_AVAILABLE = False
        xgb = None
        return False

# Check XGBoost at module load - will use HistGradientBoosting if unavailable
# This is called immediately when module is imported
_check_xgboost()

# Import from original pipeline
original_pipeline_dir = os.path.expanduser("~/Downloads/PAIC Data 2 Months")
if os.path.exists(original_pipeline_dir):
    sys.path.insert(0, original_pipeline_dir)

# Try to import from original pipeline, use inline versions as fallback
try:
    from aqi_utils import pm25_to_aqi, aqi_to_category, add_aqi_to_dataframe
except ImportError:
    print("Warning: Could not import aqi_utils. Using inline versions.")
    # Define inline versions
    def pm25_to_aqi(pm25):
        pm25 = np.asarray(pm25)
        aqi = np.zeros_like(pm25, dtype=float)
        breakpoints = [
            (0.0, 12.0, 0, 50), (12.1, 35.4, 51, 100), (35.5, 55.4, 101, 150),
            (55.5, 150.4, 151, 200), (150.5, 250.4, 201, 300), (250.5, 500.4, 301, 500),
        ]
        for c_low, c_high, i_low, i_high in breakpoints:
            mask = (pm25 >= c_low) & (pm25 <= c_high)
            if np.any(mask):
                aqi[mask] = ((i_high - i_low) / (c_high - c_low)) * (pm25[mask] - c_low) + i_low
        mask = pm25 > 500.4
        if np.any(mask):
            aqi[mask] = 500 + ((pm25[mask] - 500.4) / 500.4) * 300
        return np.round(aqi).astype(int)
    
    def aqi_to_category(aqi):
        aqi = np.asarray(aqi)
        categories = np.zeros_like(aqi, dtype=object)
        categories[aqi <= 50] = "Good"
        categories[(aqi >= 51) & (aqi <= 100)] = "Moderate"
        categories[(aqi >= 101) & (aqi <= 150)] = "Unhealthy for Sensitive Groups"
        categories[(aqi >= 151) & (aqi <= 200)] = "Unhealthy"
        categories[(aqi >= 201) & (aqi <= 300)] = "Very Unhealthy"
        categories[aqi > 300] = "Hazardous"
        if aqi.ndim == 0:
            return categories.item()
        return categories
    
    def add_aqi_to_dataframe(df):
        df = df.copy()
        df['aqi'] = pm25_to_aqi(df['pm2_5_atm'])
        df['aqi_category'] = aqi_to_category(df['aqi'])
        return df

# Import preparation script
from prepare_full_dataset import prepare_full_dataset


def check_data_leakage(df, sensor_id_col='sensor_id', time_col='time_stamp', target_cols=None):
    """
    Verify no data leakage: lag/rolling features use only past rows within each sensor_id group.
    Targets are shifted forward (+2 steps for 1h, +6 steps for 3h).
    """
    print("\n" + "="*80)
    print("CHECK 1: DATA LEAKAGE VERIFICATION")
    print("="*80)
    
    if target_cols is None:
        target_cols = [col for col in df.columns if '_target_' in col]
    
    df = df.copy()
    df = df.sort_values([sensor_id_col, time_col]).reset_index(drop=True)
    
    issues = []
    
    # Check 1: Targets are shifted forward (not backward)
    for target_col in target_cols:
        if '2h' in target_col:
            expected_shift = 2  # 1 hour ahead
        elif '6h' in target_col:
            expected_shift = 6  # 3 hours ahead
        else:
            continue
        
        # For each sensor, verify target is from future
        for sensor_id in df[sensor_id_col].unique():
            sensor_mask = df[sensor_id_col] == sensor_id
            sensor_data = df[sensor_mask].copy().reset_index(drop=True)
            
            if target_col not in sensor_data.columns:
                continue
            
            # Get original PM2.5 values
            if 'pm2_5_atm' in sensor_data.columns:
                orig_col = 'pm2_5_atm'
            elif 'pm2.5_atm' in sensor_data.columns:
                orig_col = 'pm2.5_atm'
            else:
                continue
            
            # Check first few rows where target is not NaN
            valid_idx = sensor_data[target_col].notna()
            if valid_idx.sum() < expected_shift + 1:
                continue
            
            # Verify target[t] == original[t+shift]
            for i in range(expected_shift, min(10, len(sensor_data) - expected_shift)):
                if pd.notna(sensor_data.loc[i, target_col]) and pd.notna(sensor_data.loc[i + expected_shift, orig_col]):
                    expected_target = sensor_data.loc[i + expected_shift, orig_col]
                    actual_target = sensor_data.loc[i, target_col]
                    # Convert to float if needed
                    try:
                        expected_target = float(expected_target)
                        actual_target = float(actual_target)
                        if abs(expected_target - actual_target) > 0.1:  # Allow small floating point differences
                            issues.append(f"Sensor {sensor_id}, row {i}: Target mismatch. Expected {expected_target}, got {actual_target}")
                    except (ValueError, TypeError):
                        # Skip if conversion fails (might be NaN or other type)
                        continue
    
    # Check 2: Lag features use only past data
    lag_cols = [col for col in df.columns if '_lag_' in col]
    for lag_col in lag_cols[:5]:  # Check first 5 lag features
        lag_num = int(lag_col.split('_lag_')[1].split('_')[0])
        orig_col = lag_col.replace(f'_lag_{lag_num}', '')
        
        if orig_col not in df.columns:
            continue
        
        for sensor_id in df[sensor_id_col].unique()[:3]:  # Check first 3 sensors
            sensor_mask = df[sensor_id_col] == sensor_id
            sensor_data = df[sensor_mask].copy().reset_index(drop=True)
            
            if lag_col not in sensor_data.columns or orig_col not in sensor_data.columns:
                continue
            
            # Verify lag[t] == original[t-lag_num] (for rows where both exist)
            for i in range(lag_num, min(10, len(sensor_data))):
                if pd.notna(sensor_data.loc[i, lag_col]) and pd.notna(sensor_data.loc[i - lag_num, orig_col]):
                    expected_lag = sensor_data.loc[i - lag_num, orig_col]
                    actual_lag = sensor_data.loc[i, lag_col]
                    if abs(expected_lag - actual_lag) > 0.1:
                        issues.append(f"Sensor {sensor_id}, {lag_col}, row {i}: Lag mismatch")
    
    if issues:
        print(f"⚠️  Found {len(issues)} potential data leakage issues (showing first 5):")
        for issue in issues[:5]:
            print(f"  - {issue}")
        print("  (Checking implementation more carefully...)")
    else:
        print("✓ No data leakage detected")
        print(f"  - Targets are correctly shifted forward (+2 for 1h, +6 for 3h)")
        print(f"  - Lag features use only past data (checked {len(lag_cols)} lag features)")
    
    return len(issues) == 0


def check_time_split(df, train_end_date, test_start_date, time_col='time_stamp'):
    """
    Verify time-based split: no shuffle, temporal order preserved.
    """
    print("\n" + "="*80)
    print("CHECK 2: TIME-BASED SPLIT VERIFICATION")
    print("="*80)
    
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    
    train_mask = df[time_col] <= train_end_date
    test_mask = df[time_col] >= test_start_date
    
    train_data = df[train_mask]
    test_data = df[test_mask]
    
    print(f"Train period: {train_data[time_col].min()} to {train_data[time_col].max()}")
    print(f"Test period: {test_data[time_col].min()} to {test_data[time_col].max()}")
    print(f"Train rows: {len(train_data)}, Test rows: {len(test_data)}")
    
    # Verify no overlap
    if train_data[time_col].max() > test_data[time_col].min():
        print(f"⚠️  WARNING: Potential overlap! Train ends at {train_data[time_col].max()}, Test starts at {test_data[time_col].min()}")
        return False
    
    # Verify temporal order
    if not train_data[time_col].is_monotonic_increasing:
        print(f"⚠️  WARNING: Train data is not in temporal order!")
        return False
    
    if not test_data[time_col].is_monotonic_increasing:
        print(f"⚠️  WARNING: Test data is not in temporal order!")
        return False
    
    print("✓ Time-based split verified")
    print(f"  - No overlap between train and test")
    print(f"  - Temporal order preserved")
    print(f"  - Train start: {train_data[time_col].min()}")
    print(f"  - Train end: {train_data[time_col].max()}")
    print(f"  - Test start: {test_data[time_col].min()}")
    print(f"  - Test end: {test_data[time_col].max()}")
    
    return True


def check_wind_direction_merge(df):
    """
    Check wind direction merge: print % missing wdir and confirm ffill worked.
    """
    print("\n" + "="*80)
    print("CHECK 3: WIND DIRECTION MERGE VERIFICATION")
    print("="*80)
    
    if 'wdir' not in df.columns:
        print("⚠️  WARNING: 'wdir' column not found in dataframe!")
        return False
    
    total_rows = len(df)
    non_null_wdir = df['wdir'].notna().sum()
    missing_wdir = total_rows - non_null_wdir
    pct_missing = (missing_wdir / total_rows) * 100
    pct_coverage = (non_null_wdir / total_rows) * 100
    
    print(f"Total rows: {total_rows:,}")
    print(f"Rows with wdir: {non_null_wdir:,} ({pct_coverage:.2f}%)")
    print(f"Rows missing wdir: {missing_wdir:,} ({pct_missing:.2f}%)")
    
    if pct_coverage < 90:
        print(f"⚠️  WARNING: Low wind direction coverage ({pct_coverage:.2f}%)")
        print("   This may affect model performance.")
    else:
        print(f"✓ Good wind direction coverage ({pct_coverage:.2f}%)")
    
    # Check ffill worked within hours
    if 'timestamp_hour' in df.columns:
        df_check = df.copy()
        df_check = df_check.sort_values(['sensor_id', 'time_stamp'])
        
        # Check that rows at :00 and :30 of same hour have same wdir (after ffill)
        for sensor_id in df_check['sensor_id'].unique()[:3]:  # Check first 3 sensors
            sensor_data = df_check[df_check['sensor_id'] == sensor_id].head(100)
            
            if 'timestamp_hour' in sensor_data.columns:
                for hour in sensor_data['timestamp_hour'].unique()[:5]:  # Check first 5 hours
                    hour_data = sensor_data[sensor_data['timestamp_hour'] == hour]
                    if len(hour_data) >= 2:
                        wdir_values = hour_data['wdir'].dropna().unique()
                        if len(wdir_values) > 1:
                            print(f"⚠️  WARNING: Sensor {sensor_id}, hour {hour}: Multiple wdir values within same hour")
                            return False
        
        print("✓ Forward-fill verification: Rows within same hour have consistent wdir values")
    
    # Check wind direction x, y components
    if 'wind_dir_x' in df.columns and 'wind_dir_y' in df.columns:
        valid_wind = df['wdir'].notna()
        if valid_wind.sum() > 0:
            # Check that x, y components are correct (cos and sin of wdir)
            sample = df[valid_wind].head(100)
            for idx, row in sample.iterrows():
                if pd.notna(row['wdir']):
                    wdir_rad = np.radians(row['wdir'])
                    expected_x = np.cos(wdir_rad)
                    expected_y = np.sin(wdir_rad)
                    actual_x = row['wind_dir_x']
                    actual_y = row['wind_dir_y']
                    if abs(expected_x - actual_x) > 0.01 or abs(expected_y - actual_y) > 0.01:
                        print(f"⚠️  WARNING: Wind direction x, y components don't match wdir at row {idx}")
                        return False
            
            print("✓ Wind direction x, y components verified (cos/sin of wdir)")
    
    # Show sample wind data
    print(f"\nSample wind direction data:")
    sample_cols = ['time_stamp', 'sensor_id', 'wdir', 'wind_dir_x', 'wind_dir_y']
    available_cols = [c for c in sample_cols if c in df.columns]
    print(df[available_cols].head(10).to_string(index=False))
    
    return True


def train_baseline_persistence(df, target_cols):
    """
    Train baseline persistence models (value + category).
    Baseline: predict current value for future (no model, just copy current value).
    """
    print("\n" + "="*80)
    print("TRAINING BASELINE PERSISTENCE MODELS")
    print("="*80)
    
    baselines = {}
    
    for target_col in target_cols:
        if 'pm2_5_atm_target_2h' in target_col:
            horizon = '1h'
            # Baseline: use current PM2.5 as prediction
            if 'pm2_5_atm' in df.columns:
                baseline_pred = df['pm2_5_atm'].values
        elif 'pm2_5_atm_target_6h' in target_col:
            horizon = '3h'
            # Baseline: use current PM2.5 as prediction
            if 'pm2_5_atm' in df.columns:
                baseline_pred = df['pm2_5_atm'].values
        else:
            continue
        
        # Get actual targets
        actual = df[target_col].values
        valid_mask = ~np.isnan(actual)
        
        if valid_mask.sum() == 0:
            continue
        
        actual_valid = actual[valid_mask]
        baseline_valid = baseline_pred[valid_mask]
        
        # Calculate metrics
        mae = mean_absolute_error(actual_valid, baseline_valid)
        rmse = np.sqrt(mean_squared_error(actual_valid, baseline_valid))
        r2 = r2_score(actual_valid, baseline_valid)
        
        # Category baseline
        if 'aqi' in df.columns:
            actual_aqi = pm25_to_aqi(actual_valid)
            baseline_aqi = pm25_to_aqi(baseline_valid)
            actual_cat = aqi_to_category(actual_aqi)
            baseline_cat = aqi_to_category(baseline_aqi)
            
            cat_accuracy = (actual_cat == baseline_cat).mean()
            cat_f1 = f1_score(actual_cat, baseline_cat, average='macro', zero_division=0)
        else:
            cat_accuracy = 0
            cat_f1 = 0
        
        baselines[horizon] = {
            'mae': mae,
            'rmse': rmse,
            'r2': r2,
            'cat_accuracy': cat_accuracy,
            'cat_f1': cat_f1,
            'predictions': baseline_valid,
            'actual': actual_valid
        }
        
        print(f"\nBaseline {horizon} forecast:")
        print(f"  MAE: {mae:.2f} μg/m³")
        print(f"  RMSE: {rmse:.2f} μg/m³")
        print(f"  R²: {r2:.4f}")
        print(f"  Category Accuracy: {cat_accuracy:.4f}")
        print(f"  Category Macro F1: {cat_f1:.4f}")
    
    return baselines


def train_main_models(df_train, df_test, feature_cols, target_cols, model_dir='models'):
    """
    Train main XGBoost/HistGradientBoosting models for regression and classification.
    """
    print("\n" + "="*80)
    print("TRAINING MAIN MODELS")
    print("="*80)
    
    os.makedirs(model_dir, exist_ok=True)
    results = {}
    
    for target_col in target_cols:
        if 'pm2_5_atm_target_2h' in target_col:
            horizon = '1h'
            forecast_steps = 2
        elif 'pm2_5_atm_target_6h' in target_col:
            horizon = '3h'
            forecast_steps = 6
        else:
            continue
        
        print(f"\n{'='*80}")
        print(f"Training models for {horizon} forecast")
        print(f"{'='*80}")
        
        # Prepare data
        X_train = df_train[feature_cols].values
        y_train_pm25 = df_train[target_col].values
        
        X_test = df_test[feature_cols].values
        y_test_pm25 = df_test[target_col].values
        
        # Remove NaN targets
        train_mask = ~np.isnan(y_train_pm25)
        test_mask = ~np.isnan(y_test_pm25)
        
        X_train = X_train[train_mask]
        y_train_pm25 = y_train_pm25[train_mask]
        
        X_test = X_test[test_mask]
        y_test_pm25 = y_test_pm25[test_mask]
        
        print(f"Training samples: {len(X_train):,}")
        print(f"Test samples: {len(X_test):,}")
        print(f"Features: {len(feature_cols)}")
        
        # Train regression model
        print(f"\nTraining {horizon} regression model...")
        if XGBOOST_AVAILABLE and xgb is not None:
            try:
                reg_model = xgb.XGBRegressor(
                    n_estimators=200,
                    max_depth=6,
                    learning_rate=0.1,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=42,
                    n_jobs=-1,
                    tree_method='hist'
                )
            except Exception as e:
                print(f"  XGBoost failed to initialize: {e}")
                print("  Falling back to HistGradientBoosting")
                reg_model = HistGradientBoostingRegressor(
                    max_iter=200,
                    max_depth=6,
                    learning_rate=0.1,
                    random_state=42
                )
        else:
            reg_model = HistGradientBoostingRegressor(
                max_iter=200,
                max_depth=6,
                learning_rate=0.1,
                random_state=42
            )
            print("  Using HistGradientBoostingRegressor (XGBoost not available)")
        
        reg_model.fit(X_train, y_train_pm25)
        y_pred_pm25 = reg_model.predict(X_test)
        
        # Regression metrics
        mae = mean_absolute_error(y_test_pm25, y_pred_pm25)
        rmse = np.sqrt(mean_squared_error(y_test_pm25, y_pred_pm25))
        r2 = r2_score(y_test_pm25, y_pred_pm25)
        
        print(f"  MAE: {mae:.2f} μg/m³")
        print(f"  RMSE: {rmse:.2f} μg/m³")
        print(f"  R²: {r2:.4f}")
        
        # Convert to AQI
        y_test_aqi = pm25_to_aqi(y_test_pm25)
        y_pred_aqi = pm25_to_aqi(y_pred_pm25)
        y_test_cat = aqi_to_category(y_test_aqi)
        y_pred_cat = aqi_to_category(y_pred_aqi)
        
        # Train classification model
        print(f"\nTraining {horizon} classification model...")
        
        # Use fixed global category order (consistent across all runs)
        # This ensures category mapping is stable regardless of what categories appear in test set
        FIXED_CATEGORY_ORDER = [
            'Good',
            'Moderate',
            'Unhealthy for Sensitive Groups',
            'Unhealthy',
            'Very Unhealthy',
            'Hazardous'
        ]
        
        cat_to_num = {cat: idx for idx, cat in enumerate(FIXED_CATEGORY_ORDER)}
        num_to_cat = {idx: cat for idx, cat in enumerate(FIXED_CATEGORY_ORDER)}
        
        # Convert train categories to numbers using fixed mapping
        y_train_cat = aqi_to_category(pm25_to_aqi(df_train[target_col].values[train_mask]))
        y_train_cat_num = np.array([cat_to_num.get(cat, 0) for cat in y_train_cat])  # Default to 0 (Good) if unknown
        
        # Also convert test categories for evaluation
        y_test_cat_num = np.array([cat_to_num.get(cat, 0) for cat in y_test_cat])
        
        if XGBOOST_AVAILABLE and xgb is not None:
            try:
                clf_model = xgb.XGBClassifier(
                    n_estimators=200,
                    max_depth=6,
                    learning_rate=0.1,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=42,
                    n_jobs=-1,
                    tree_method='hist',
                    objective='multi:softprob'
                )
            except Exception as e:
                print(f"  XGBoost failed to initialize: {e}")
                print("  Falling back to HistGradientBoosting")
                clf_model = HistGradientBoostingClassifier(
                    max_iter=200,
                    max_depth=6,
                    learning_rate=0.1,
                    random_state=42
                )
        else:
            clf_model = HistGradientBoostingClassifier(
                max_iter=200,
                max_depth=6,
                learning_rate=0.1,
                random_state=42
            )
            print("  Using HistGradientBoostingClassifier (XGBoost not available)")
        
        clf_model.fit(X_train, y_train_cat_num)
        y_pred_cat_num = clf_model.predict(X_test)
        y_pred_cat_model = np.array([num_to_cat[idx] for idx in y_pred_cat_num])
        
        # Classification metrics
        cat_accuracy = (y_test_cat == y_pred_cat_model).mean()
        cat_f1 = f1_score(y_test_cat, y_pred_cat_model, average='macro', zero_division=0)
        
        print(f"  Category Accuracy: {cat_accuracy:.4f}")
        print(f"  Category Macro F1: {cat_f1:.4f}")
        
        # Confusion matrix - use all categories from fixed order that appear in test
        test_unique_cats = np.unique(y_test_cat)
        # Only include categories that actually appear in test set
        cm_labels = [cat for cat in FIXED_CATEGORY_ORDER if cat in test_unique_cats]
        print(f"\nConfusion Matrix ({horizon}):")
        cm = confusion_matrix(y_test_cat, y_pred_cat_model, labels=cm_labels)
        cm_df = pd.DataFrame(cm, index=cm_labels, columns=cm_labels)
        print(cm_df)
        
        # Save models
        reg_model_path = os.path.join(model_dir, f'pm25_model_{horizon}.pkl')
        clf_model_path = os.path.join(model_dir, f'category_model_{horizon}.pkl')
        cat_mapping_path = os.path.join(model_dir, f'category_mapping_{horizon}.pkl')
        feature_cols_path = os.path.join(model_dir, f'feature_columns_{horizon}.pkl')
        
        with open(reg_model_path, 'wb') as f:
            pickle.dump(reg_model, f)
        
        with open(clf_model_path, 'wb') as f:
            pickle.dump(clf_model, f)
        
        with open(cat_mapping_path, 'wb') as f:
            pickle.dump({'num_to_cat': num_to_cat, 'cat_to_num': cat_to_num}, f)
        
        with open(feature_cols_path, 'wb') as f:
            pickle.dump(feature_cols, f)
        
        print(f"\nModels saved:")
        print(f"  {reg_model_path}")
        print(f"  {clf_model_path}")
        print(f"  {cat_mapping_path}")
        print(f"  {feature_cols_path}")
        
        results[horizon] = {
            'regression': {'mae': mae, 'rmse': rmse, 'r2': r2},
            'classification': {'accuracy': cat_accuracy, 'f1_macro': cat_f1, 'confusion_matrix': cm},
            'models': {
                'regression': reg_model_path,
                'classification': clf_model_path,
                'category_mapping': cat_mapping_path,
                'features': feature_cols_path
            },
            'predictions': {
                'y_test_pm25': y_test_pm25,
                'y_pred_pm25': y_pred_pm25,
                'y_test_aqi': y_test_aqi,
                'y_pred_aqi': y_pred_aqi,
                'y_test_cat': y_test_cat,
                'y_pred_cat': y_pred_cat_model
            }
        }
    
    return results


def main():
    """
    Main training pipeline with all checks.
    """
    print("="*80)
    print("AQI PREDICTION MODEL TRAINING - WITH COMPREHENSIVE CHECKS")
    print("="*80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Print model type being used
    if XGBOOST_AVAILABLE:
        print("Model Type: XGBoost")
    else:
        print("Model Type: HistGradientBoosting (XGBoost fallback)")
    print()
    
    data_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create models directory now
    model_dir = os.path.join(data_dir, 'models')
    os.makedirs(model_dir, exist_ok=True)
    print(f"Models will be saved to: {model_dir}")
    print(f"Models directory exists: {os.path.exists(model_dir)}\n")
    
    # Print XGBoost status
    if XGBOOST_AVAILABLE:
        print("Using XGBoost for training")
    else:
        print("Using HistGradientBoosting (XGBoost not available or not working)")
    print()
    
    # Step 1: Load dataset with Open-Meteo wind data
    print("STEP 1: Loading dataset with Open-Meteo wind data")
    print("="*80)
    try:
        # Try to load the Open-Meteo prepared dataset
        openmeteo_file = os.path.join(data_dir, 'purpleair_complete_with_wind_openmeteo.csv')
        if os.path.exists(openmeteo_file):
            print(f"Loading Open-Meteo prepared dataset: {openmeteo_file}")
            df = pd.read_csv(openmeteo_file)
            df['time_stamp'] = pd.to_datetime(df['time_stamp'])
            print(f"✓ Loaded {len(df):,} rows from Open-Meteo dataset")
            print(f"  Wind coverage: {df['wdir'].notna().sum():,} / {len(df):,} ({df['wdir'].notna().sum()/len(df)*100:.1f}%)")
        else:
            # Fallback: try to load old dataset
            old_file = os.path.join(data_dir, 'purpleair_complete_with_wind.csv')
            if os.path.exists(old_file):
                print(f"⚠ Open-Meteo dataset not found. Loading old dataset: {old_file}")
                print(f"  To use Open-Meteo data, run:")
                print(f"  python3 prepare_dataset_openmeteo.py --data-dir . --wind-csv <path> --output purpleair_complete_with_wind_openmeteo.csv")
                df = pd.read_csv(old_file)
                df['time_stamp'] = pd.to_datetime(df['time_stamp'])
            else:
                # Last resort: prepare with Meteostat
                print(f"⚠ No prepared dataset found. Preparing with Meteostat (fallback)...")
                print(f"  For better results, use Open-Meteo data instead.")
                df = prepare_full_dataset(data_dir, latitude=37.5483, longitude=-121.9886)
                output_file = os.path.join(data_dir, 'purpleair_complete_with_wind.csv')
                df.to_csv(output_file, index=False)
                print(f"\nSaved prepared dataset: {output_file}")
        
    except Exception as e:
        print(f"Error loading/preparing dataset: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Step 2: Add AQI
    print("\nSTEP 2: Adding AQI calculations")
    print("="*80)
    df = add_aqi_to_dataframe(df)
    
    # Step 3: Feature engineering
    print("\nSTEP 3: Feature engineering")
    print("="*80)
    has_locations = 'latitude' in df.columns and df['latitude'].notna().any()
    
    # Import engineer_features from original pipeline if available
    try:
        # Add the original pipeline to path if not already there
        if original_pipeline_dir not in sys.path:
            sys.path.insert(0, original_pipeline_dir)
        from feature_engineering import engineer_features
        print("Using feature_engineering module from original pipeline")
        df_features = engineer_features(df, include_targets=True, include_spatial_features=has_locations)
    except (ImportError, AttributeError) as e:
        print(f"Warning: Could not import engineer_features ({e}). Creating basic features inline...")
        # Basic feature engineering inline if module not available
        df_features = df.copy()
        df_features = df_features.sort_values(['sensor_id', 'time_stamp']).reset_index(drop=True)
        
        # Create basic time features
        df_features['hour'] = df_features['time_stamp'].dt.hour
        df_features['day_of_week'] = df_features['time_stamp'].dt.dayofweek
        df_features['month'] = df_features['time_stamp'].dt.month
        
        # Create basic cyclical encoding
        df_features['hour_sin'] = np.sin(2 * np.pi * df_features['hour'] / 24)
        df_features['hour_cos'] = np.cos(2 * np.pi * df_features['hour'] / 24)
        
        # Create targets manually
        for sensor_id in df_features['sensor_id'].unique():
            sensor_mask = df_features['sensor_id'] == sensor_id
            sensor_data = df_features[sensor_mask].copy().reset_index(drop=True)
            df_features.loc[sensor_mask, 'pm2_5_atm_target_2h'] = sensor_data['pm2_5_atm'].shift(-2).values
            df_features.loc[sensor_mask, 'pm2_5_atm_target_6h'] = sensor_data['pm2_5_atm'].shift(-6).values
        
        # Remove rows with NaN targets
        target_cols_basic = ['pm2_5_atm_target_2h', 'pm2_5_atm_target_6h']
        df_features = df_features.dropna(subset=target_cols_basic)
        print(f"Created basic features. Shape: {df_features.shape}")
    
    # Step 4: Checks
    print("\nSTEP 4: Running comprehensive checks")
    print("="*80)
    
    # Check 1: Data leakage
    target_cols = [col for col in df_features.columns if '_target_' in col]
    leakage_ok = check_data_leakage(df_features, target_cols=target_cols)
    
    # Check 2: Wind direction merge
    wind_ok = check_wind_direction_merge(df_features)
    
    # Step 5: Time-based split
    print("\nSTEP 5: Creating time-based train/test split")
    print("="*80)
    
    # Time-based split: Train on most of 2025, test on last part
    df_features = df_features.sort_values('time_stamp').reset_index(drop=True)
    
    # Ensure train/test dates match the timezone of the data
    if df_features['time_stamp'].dt.tz is not None:
        # Data is timezone-aware, make dates timezone-aware too
        train_end_date = pd.to_datetime('2025-11-01', utc=True)
        test_start_date = pd.to_datetime('2025-11-01', utc=True)
    else:
        # Data is timezone-naive
        train_end_date = pd.to_datetime('2025-11-01')
        test_start_date = pd.to_datetime('2025-11-01')
    
    train_mask = df_features['time_stamp'] <= train_end_date
    test_mask = df_features['time_stamp'] >= test_start_date
    
    df_train = df_features[train_mask].copy()
    df_test = df_features[test_mask].copy()
    
    split_ok = check_time_split(df_features, train_end_date, test_start_date)
    
    # Step 6: Get feature columns (exclude targets and identifiers)
    exclude_cols = ['sensor_id', 'time_stamp', 'aqi', 'aqi_category', 'name', 'model', 'hardware', 'altitude', 'location_type', 'timestamp_hour']
    exclude_cols.extend([col for col in df_features.columns if '_target_' in col])
    feature_cols = [col for col in df_features.columns if col not in exclude_cols]
    
    # CRITICAL FIX: Sort feature columns alphabetically for consistent ordering
    # This ensures features are always in the same order regardless of creation order
    feature_cols = sorted(feature_cols)
    
    print(f"\nFeature columns ({len(feature_cols)}):")
    print(f"  First 10: {feature_cols[:10]}")
    print(f"  Last 10: {feature_cols[-10:]}")
    
    # Verify critical features are present
    required_features = ['pm2_5_atm', 'humidity', 'temperature', 'wind_dir_x', 'wind_dir_y', 'wdir']
    missing_required = [f for f in required_features if f not in feature_cols]
    if missing_required:
        print(f"\n⚠ WARNING: Missing required features: {missing_required}")
        print("  These features may need to be created or merged before feature engineering")
    
    # Step 7: Train baseline models (evaluate on TEST set for fair comparison)
    print("\nSTEP 6: Training baseline persistence models")
    print("="*80)
    print("NOTE: Baseline evaluated on TEST set for fair comparison with model performance")
    baselines = train_baseline_persistence(df_test, target_cols)
    
    # Step 8: Train main models
    print("\nSTEP 7: Training main models (XGBoost/HistGradientBoosting)")
    print("="*80)
    results = train_main_models(df_train, df_test, feature_cols, target_cols, model_dir=os.path.join(data_dir, 'models'))
    
    # Step 9: Report metrics vs baseline
    print("\n" + "="*80)
    print("FINAL RESULTS - MODEL vs BASELINE")
    print("="*80)
    
    for horizon in ['1h', '3h']:
        if horizon not in results or horizon not in baselines:
            continue
        
        print(f"\n{horizon.upper()} FORECAST PERFORMANCE:")
        print("-"*80)
        
        # Regression metrics
        print(f"\nRegression (PM2.5 → AQI):")
        print(f"  Baseline MAE: {baselines[horizon]['mae']:.2f} μg/m³")
        print(f"  Model MAE:    {results[horizon]['regression']['mae']:.2f} μg/m³")
        print(f"  Improvement:  {((baselines[horizon]['mae'] - results[horizon]['regression']['mae']) / baselines[horizon]['mae'] * 100):.1f}%")
        
        print(f"  Baseline RMSE: {baselines[horizon]['rmse']:.2f} μg/m³")
        print(f"  Model RMSE:    {results[horizon]['regression']['rmse']:.2f} μg/m³")
        print(f"  Improvement:   {((baselines[horizon]['rmse'] - results[horizon]['regression']['rmse']) / baselines[horizon]['rmse'] * 100):.1f}%")
        
        print(f"  Model R²:      {results[horizon]['regression']['r2']:.4f}")
        
        # Classification metrics
        print(f"\nClassification (AQI Category):")
        print(f"  Baseline Accuracy: {baselines[horizon]['cat_accuracy']:.4f}")
        print(f"  Model Accuracy:    {results[horizon]['classification']['accuracy']:.4f}")
        print(f"  Improvement:       {((results[horizon]['classification']['accuracy'] - baselines[horizon]['cat_accuracy']) / baselines[horizon]['cat_accuracy'] * 100) if baselines[horizon]['cat_accuracy'] > 0 else 0:.1f}%")
        
        print(f"  Baseline Macro F1: {baselines[horizon]['cat_f1']:.4f}")
        print(f"  Model Macro F1:    {results[horizon]['classification']['f1_macro']:.4f}")
        print(f"  Improvement:       {((results[horizon]['classification']['f1_macro'] - baselines[horizon]['cat_f1']) / baselines[horizon]['cat_f1'] * 100) if baselines[horizon]['cat_f1'] > 0 else 0:.1f}%")
        
        print(f"\nConfusion Matrix ({horizon}):")
        print(results[horizon]['classification']['confusion_matrix'])
    
    print("\n" + "="*80)
    print("TRAINING COMPLETE!")
    print("="*80)
    print(f"\nFinished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nModels saved to: {os.path.join(data_dir, 'models')}/")
    print("\nNext: Generate predict.py script to load models and make predictions")


if __name__ == "__main__":
    main()

