"""
Phase 2: Step 6 - Train v2 Model
Trains XGBoost regression and classification models using time-based train/val/test splits.
"""

import pandas as pd
import numpy as np
import pickle
import os
import sys
from pathlib import Path
from datetime import datetime
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, classification_report, confusion_matrix
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import AQI utilities
try:
    from aqi_utils import pm25_to_aqi, aqi_to_category
except ImportError:
    # Fallback if aqi_utils not available
    def pm25_to_aqi(pm25):
        """Convert PM2.5 to AQI (simplified)."""
        pm25 = np.array(pm25)
        aqi = np.where(pm25 <= 12.0, (pm25 / 12.0) * 50,
              np.where(pm25 <= 35.4, ((pm25 - 12.1) / (35.4 - 12.1)) * 50 + 50,
              np.where(pm25 <= 55.4, ((pm25 - 35.5) / (55.4 - 35.5)) * 50 + 100,
              np.where(pm25 <= 150.4, ((pm25 - 55.5) / (150.4 - 55.5)) * 50 + 150,
              np.where(pm25 <= 250.4, ((pm25 - 150.5) / (250.4 - 150.5)) * 100 + 200,
              ((pm25 - 250.5) / (350.4 - 250.5)) * 100 + 300)))))
        return aqi
    
    def aqi_to_category(aqi):
        """Convert AQI to category."""
        aqi = np.array(aqi)
        return np.where(aqi <= 50, 'Good',
               np.where(aqi <= 100, 'Moderate',
               np.where(aqi <= 150, 'Unhealthy for Sensitive Groups',
               np.where(aqi <= 200, 'Unhealthy',
               np.where(aqi <= 300, 'Very Unhealthy', 'Hazardous')))))


def get_feature_columns(df, exclude_cols=None):
    """Get list of feature columns, excluding targets and identifiers."""
    if exclude_cols is None:
        exclude_cols = []
    
    exclude = ['sensor_id', 'time_stamp', 'aqi', 'aqi_category', 'name', 'model', 
               'hardware', 'altitude', 'location_type']
    exclude.extend([col for col in df.columns if '_target_' in col])
    exclude.extend(exclude_cols)
    
    feature_cols = [col for col in df.columns if col not in exclude]
    return feature_cols


def train_pm25_model(X_train, y_train, X_val, y_val, model_name='pm25'):
    """
    Train XGBoost model to predict PM2.5 values.
    
    Returns:
        Trained model and evaluation metrics
    """
    print(f"\nTraining {model_name} model...")
    print(f"Training samples: {len(X_train):,}")
    print(f"Validation samples: {len(X_val):,}")
    print(f"Features: {X_train.shape[1]}")
    
    # XGBoost parameters (same as v1 for comparability)
    params = {
        'objective': 'reg:squarederror',
        'n_estimators': 200,
        'max_depth': 6,
        'learning_rate': 0.1,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'min_child_weight': 3,
        'gamma': 0.1,
        'random_state': 42,
        'n_jobs': -1,
        'tree_method': 'hist'
    }
    
    model = xgb.XGBRegressor(**params)
    
    # Train on training set
    model.fit(X_train, y_train, 
              eval_set=[(X_train, y_train), (X_val, y_val)],
              verbose=False)
    
    # Evaluate on validation set
    y_pred_train = model.predict(X_train)
    y_pred_val = model.predict(X_val)
    
    train_mae = mean_absolute_error(y_train, y_pred_train)
    train_rmse = np.sqrt(mean_squared_error(y_train, y_pred_train))
    train_r2 = r2_score(y_train, y_pred_train)
    
    val_mae = mean_absolute_error(y_val, y_pred_val)
    val_rmse = np.sqrt(mean_squared_error(y_val, y_pred_val))
    val_r2 = r2_score(y_val, y_pred_val)
    
    print(f"Training   MAE: {train_mae:.2f} μg/m³, RMSE: {train_rmse:.2f}, R²: {train_r2:.4f}")
    print(f"Validation MAE: {val_mae:.2f} μg/m³, RMSE: {val_rmse:.2f}, R²: {val_r2:.4f}")
    
    metrics = {
        'train_mae': train_mae,
        'train_rmse': train_rmse,
        'train_r2': train_r2,
        'val_mae': val_mae,
        'val_rmse': val_rmse,
        'val_r2': val_r2
    }
    
    return model, metrics


def train_category_model(X_train, y_train_pm25, X_val, y_val_pm25, model_name='aqi_category'):
    """
    Train XGBoost classifier to predict AQI category.
    """
    print(f"\nTraining {model_name} classification model...")
    
    # Convert PM2.5 to AQI and categories
    train_aqi = pm25_to_aqi(y_train_pm25)
    train_categories = aqi_to_category(train_aqi)
    
    val_aqi = pm25_to_aqi(y_val_pm25)
    val_categories = aqi_to_category(val_aqi)
    
    # Get unique categories
    all_categories = np.unique(np.concatenate([train_categories, val_categories]))
    category_to_num = {cat: idx for idx, cat in enumerate(all_categories)}
    num_to_category = {idx: cat for cat, idx in category_to_num.items()}
    
    y_train_numeric = np.array([category_to_num[cat] for cat in train_categories])
    y_val_numeric = np.array([category_to_num[cat] for cat in val_categories])
    
    params = {
        'objective': 'multi:softprob',
        'n_estimators': 200,
        'max_depth': 6,
        'learning_rate': 0.1,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'random_state': 42,
        'n_jobs': -1,
        'tree_method': 'hist'
    }
    
    model = xgb.XGBClassifier(**params)
    
    # Train
    model.fit(X_train, y_train_numeric,
              eval_set=[(X_train, y_train_numeric), (X_val, y_val_numeric)],
              verbose=False)
    
    # Evaluate
    y_pred_train = model.predict(X_train)
    y_pred_val = model.predict(X_val)
    
    train_acc = (y_pred_train == y_train_numeric).mean()
    val_acc = (y_pred_val == y_val_numeric).mean()
    
    print(f"Training   Accuracy: {train_acc:.4f}")
    print(f"Validation Accuracy: {val_acc:.4f}")
    
    print("\nValidation Classification Report:")
    print(classification_report(val_categories, 
                                [num_to_category[idx] for idx in y_pred_val]))
    
    metrics = {
        'category_mapping': num_to_category,
        'train_accuracy': train_acc,
        'val_accuracy': val_acc
    }
    
    return model, metrics


def train_models_for_horizon(df_train, df_val, df_test, horizon_hours, model_dir):
    """
    Train models for a specific forecast horizon.
    
    Returns:
        Dictionary with trained models and metrics
    """
    horizon_steps = horizon_hours * 2  # Convert hours to 30-min steps
    target_col = f'pm2_5_atm_target_{horizon_steps}h'
    
    if target_col not in df_train.columns:
        raise ValueError(f"Target column {target_col} not found")
    
    # Get feature columns
    feature_cols = get_feature_columns(df_train)
    print(f"\nUsing {len(feature_cols)} features")
    
    # Prepare data
    X_train = df_train[feature_cols].values
    y_train = df_train[target_col].values
    
    X_val = df_val[feature_cols].values
    y_val = df_val[target_col].values
    
    X_test = df_test[feature_cols].values
    y_test = df_test[target_col].values
    
    # Remove NaN targets
    train_mask = ~np.isnan(y_train)
    val_mask = ~np.isnan(y_val)
    test_mask = ~np.isnan(y_test)
    
    X_train = X_train[train_mask]
    y_train = y_train[train_mask]
    
    X_val = X_val[val_mask]
    y_val = y_val[val_mask]
    
    X_test = X_test[test_mask]
    y_test = y_test[test_mask]
    
    print(f"\n{'='*70}")
    print(f"Training models for {horizon_hours}-hour forecast horizon")
    print(f"{'='*70}")
    print(f"Train samples: {len(X_train):,}")
    print(f"Val samples:   {len(X_val):,}")
    print(f"Test samples:  {len(X_test):,}")
    
    # Train PM2.5 regression model
    pm25_model, pm25_metrics = train_pm25_model(
        X_train, y_train, X_val, y_val,
        model_name=f'pm25_{horizon_hours}h'
    )
    
    # Train category classification model
    category_model, category_metrics = train_category_model(
        X_train, y_train, X_val, y_val,
        model_name=f'category_{horizon_hours}h'
    )
    
    # Evaluate on test set
    print(f"\n{'='*70}")
    print(f"Test Set Evaluation ({horizon_hours}-hour forecast)")
    print(f"{'='*70}")
    
    y_test_pred_pm25 = pm25_model.predict(X_test)
    test_mae = mean_absolute_error(y_test, y_test_pred_pm25)
    test_rmse = np.sqrt(mean_squared_error(y_test, y_test_pred_pm25))
    test_r2 = r2_score(y_test, y_test_pred_pm25)
    
    test_aqi = pm25_to_aqi(y_test)
    test_aqi_pred = pm25_to_aqi(y_test_pred_pm25)
    test_aqi_mae = mean_absolute_error(test_aqi, test_aqi_pred)
    
    print(f"Test PM2.5 MAE:  {test_mae:.2f} μg/m³")
    print(f"Test PM2.5 RMSE: {test_rmse:.2f} μg/m³")
    print(f"Test PM2.5 R²:   {test_r2:.4f}")
    print(f"Test AQI MAE:   {test_aqi_mae:.2f} AQI")
    
    # Category accuracy on test set
    test_categories = aqi_to_category(test_aqi)
    test_categories_pred = aqi_to_category(test_aqi_pred)
    test_category_acc = (test_categories == test_categories_pred).mean()
    print(f"Test Category Accuracy: {test_category_acc:.4f}")
    
    # Save models
    os.makedirs(model_dir, exist_ok=True)
    
    pm25_model_file = os.path.join(model_dir, f'xgboost_regressor_{horizon_hours}h.pkl')
    category_model_file = os.path.join(model_dir, f'xgboost_classifier_{horizon_hours}h.pkl')
    
    with open(pm25_model_file, 'wb') as f:
        pickle.dump(pm25_model, f)
    print(f"\nSaved PM2.5 model to: {pm25_model_file}")
    
    with open(category_model_file, 'wb') as f:
        pickle.dump(category_model, f)
    print(f"Saved category model to: {category_model_file}")
    
    # Save feature columns for prediction
    feature_cols_file = os.path.join(model_dir, f'feature_columns_{horizon_hours}h.pkl')
    with open(feature_cols_file, 'wb') as f:
        pickle.dump(feature_cols, f)
    
    results = {
        'horizon_hours': horizon_hours,
        'pm25_model': pm25_model,
        'category_model': category_model,
        'feature_columns': feature_cols,
        'pm25_metrics': {
            **pm25_metrics,
            'test_mae': test_mae,
            'test_rmse': test_rmse,
            'test_r2': test_r2,
            'test_aqi_mae': test_aqi_mae
        },
        'category_metrics': {
            **category_metrics,
            'test_accuracy': test_category_acc
        }
    }
    
    return results


def main():
    """Main execution function."""
    # Paths
    input_file = Path(__file__).parent.parent / "data" / "processed" / "dataset_with_features.csv"
    model_dir = Path(__file__).parent.parent / "models" / "v2"
    model_dir.mkdir(parents=True, exist_ok=True)
    
    print("="*70)
    print("PHASE 2: TRAINING V2 MODEL")
    print("="*70)
    
    # Load feature-engineered data
    print(f"\nLoading feature-engineered data from: {input_file}")
    df = pd.read_csv(input_file, parse_dates=['time_stamp'])
    print(f"Loaded {len(df):,} rows")
    
    # Time-based splits
    train_start = pd.Timestamp('2024-01-01')
    train_end = pd.Timestamp('2025-09-30')
    val_start = pd.Timestamp('2025-10-01')
    val_end = pd.Timestamp('2025-11-30')
    test_start = pd.Timestamp('2025-12-01')
    test_end = pd.Timestamp('2026-01-10')
    
    print(f"\n{'='*70}")
    print("TIME-BASED DATA SPLITS")
    print(f"{'='*70}")
    print(f"Train: {train_start.date()} to {train_end.date()}")
    print(f"Val:   {val_start.date()} to {val_end.date()}")
    print(f"Test:  {test_start.date()} to {test_end.date()}")
    
    # Split data
    df_train = df[(df['time_stamp'] >= train_start) & (df['time_stamp'] <= train_end)].copy()
    df_val = df[(df['time_stamp'] >= val_start) & (df['time_stamp'] <= val_end)].copy()
    df_test = df[(df['time_stamp'] >= test_start) & (df['time_stamp'] <= test_end)].copy()
    
    print(f"\nSplit sizes:")
    print(f"Train: {len(df_train):,} rows ({len(df_train)/len(df)*100:.1f}%)")
    print(f"Val:   {len(df_val):,} rows ({len(df_val)/len(df)*100:.1f}%)")
    print(f"Test:  {len(df_test):,} rows ({len(df_test)/len(df)*100:.1f}%)")
    
    # Train models for 1-hour and 3-hour horizons
    results_1h = train_models_for_horizon(df_train, df_val, df_test, 1, model_dir)
    results_3h = train_models_for_horizon(df_train, df_val, df_test, 3, model_dir)
    
    # Summary
    print(f"\n{'='*70}")
    print("TRAINING COMPLETE - V2 MODEL")
    print(f"{'='*70}")
    print(f"\nModels saved to: {model_dir}/")
    print(f"\n1-Hour Forecast Performance:")
    print(f"  Test PM2.5 MAE: {results_1h['pm25_metrics']['test_mae']:.2f} μg/m³")
    print(f"  Test AQI MAE:   {results_1h['pm25_metrics']['test_aqi_mae']:.2f} AQI")
    print(f"  Test Category Accuracy: {results_1h['category_metrics']['test_accuracy']:.4f}")
    print(f"\n3-Hour Forecast Performance:")
    print(f"  Test PM2.5 MAE: {results_3h['pm25_metrics']['test_mae']:.2f} μg/m³")
    print(f"  Test AQI MAE:   {results_3h['pm25_metrics']['test_aqi_mae']:.2f} AQI")
    print(f"  Test Category Accuracy: {results_3h['category_metrics']['test_accuracy']:.4f}")


if __name__ == "__main__":
    main()
