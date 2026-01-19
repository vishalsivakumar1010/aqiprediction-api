"""
Compute threshold-based metrics for validation results.

Metrics:
- Recall for AQI ≥ 50 (Moderate+): How often we catch when it actually happens
- Missed-Warning Rate: How often actual ≥ threshold but predicted < threshold
"""

import pandas as pd
import glob
import sys
import argparse

def compute_threshold_metrics(csv_file, threshold=50):
    """
    Compute threshold-based metrics from validation results.
    
    Args:
        csv_file: Path to validation CSV file
        threshold: AQI threshold (default: 50 for Moderate+)
        
    Returns:
        Dictionary with metrics for 1h and 3h forecasts
    """
    df = pd.read_csv(csv_file)
    
    results = {}
    
    for horizon in ['1h', '3h']:
        actual_col = f'actual_aqi_{horizon}'
        pred_col = f'pred_aqi_{horizon}'
        
        actual = df[actual_col]
        predicted = df[pred_col]
        
        # Actual ≥ threshold
        actual_above = actual >= threshold
        pred_above = predicted >= threshold
        
        # Confusion matrix
        tp = (actual_above & pred_above).sum()  # True Positives (caught)
        fn = (actual_above & ~pred_above).sum()  # False Negatives (MISSED)
        fp = (~actual_above & pred_above).sum()  # False Positives (false alarm)
        tn = (~actual_above & ~pred_above).sum()  # True Negatives
        
        # Metrics
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        missed_warning_rate = fn / (tp + fn) if (tp + fn) > 0 else 0.0
        false_alarm_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        
        results[horizon] = {
            'threshold': threshold,
            'actual_above_count': actual_above.sum(),
            'pred_above_count': pred_above.sum(),
            'tp': tp,
            'fn': fn,
            'fp': fp,
            'tn': tn,
            'recall': recall,
            'precision': precision,
            'missed_warning_rate': missed_warning_rate,
            'false_alarm_rate': false_alarm_rate
        }
    
    return results


def print_metrics(results, threshold=50):
    """Print threshold metrics in a readable format."""
    threshold_name = {
        50: 'Moderate+',
        100: 'Unhealthy for Sensitive Groups+',
        150: 'Unhealthy+'
    }.get(threshold, f'AQI ≥ {threshold}')
    
    print(f"\n{'='*80}")
    print(f"THRESHOLD METRICS: AQI ≥ {threshold} ({threshold_name})")
    print(f"{'='*80}")
    
    for horizon in ['1h', '3h']:
        m = results[horizon]
        print(f"\n{horizon.upper()} Forecast:")
        print(f"  Actual ≥ {threshold} cases: {m['actual_above_count']}")
        print(f"  Predicted ≥ {threshold} cases: {m['pred_above_count']}")
        print(f"  True Positives (caught): {m['tp']}")
        print(f"  False Negatives (MISSED): {m['fn']}")
        print(f"  False Positives (false alarm): {m['fp']}")
        print(f"  True Negatives: {m['tn']}")
        print()
        print(f"  Recall: {m['recall']:.1%} (caught {m['recall']:.1%} of actual ≥ {threshold} cases)")
        print(f"  Missed-Warning Rate: {m['missed_warning_rate']:.1%} ({m['fn']} missed out of {m['actual_above_count']} actual cases)")
        print(f"  Precision: {m['precision']:.1%} (of predicted ≥ {threshold}, {m['precision']:.1%} were correct)")
        print(f"  False Alarm Rate: {m['false_alarm_rate']:.1%} (predicted ≥ {threshold} when actual < {threshold})")


def main():
    parser = argparse.ArgumentParser(description='Compute threshold-based metrics from validation results')
    parser.add_argument('--csv', type=str, default=None, help='Path to validation CSV file (default: most recent)')
    parser.add_argument('--threshold', type=int, default=50, help='AQI threshold (default: 50)')
    
    args = parser.parse_args()
    
    # Find CSV file
    if args.csv:
        csv_file = args.csv
    else:
        csv_files = glob.glob('validation_historic_*.csv')
        if not csv_files:
            print("Error: No validation CSV files found")
            sys.exit(1)
        csv_file = max(csv_files, key=lambda f: f.split('_')[-1].replace('.csv', ''))
    
    print(f"Loading: {csv_file}")
    df = pd.read_csv(csv_file)
    print(f"Total validations: {len(df)}")
    
    # Compute metrics
    results = compute_threshold_metrics(csv_file, threshold=args.threshold)
    
    # Print results
    print_metrics(results, threshold=args.threshold)
    
    # Also compute for threshold 100 if there are any cases
    results_100 = compute_threshold_metrics(csv_file, threshold=100)
    if results_100['1h']['actual_above_count'] > 0 or results_100['3h']['actual_above_count'] > 0:
        print_metrics(results_100, threshold=100)


if __name__ == "__main__":
    main()
