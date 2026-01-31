"""
Phase 2: Step 3 - Data Quality Control Pipeline
Implements systematic QC: sample-level filtering, spike detection, stuck sensors, coverage thresholds.
"""

import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path
from datetime import datetime
import json

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))


# QC Parameters (configurable)
QC_CONFIG = {
    # Sample-level hard removals
    'pm25_min': 0,
    'pm25_max': 500,
    
    # Spike detection Stage 1 (auto-remove)
    'spike_multiplier': 10,
    'spike_min_value': 200,
    'spike_check_window': 2,  # next 2 readings (60 minutes)
    'spike_return_threshold': 0.2,  # within 20% of pre-spike
    
    # Spike detection Stage 2 (flag-only)
    'spike_flag_multiplier': 5,
    'spike_flag_min_value': 100,
    
    # Stuck sensor detection
    'stuck_window_hours': 12,  # 12 hours = 24 readings
    'stuck_std_threshold': 1.0,
    'stuck_range_threshold': 2.0,
    'stuck_identical_hours': 6,  # 6 hours = 12 readings
    
    # Sensor-level coverage
    'min_samples': 1000,
    'min_coverage_days': 90,
    'min_samples_alt': 5000,  # alternative if coverage < 90 days
    
    # Sensor drop threshold
    'sensor_drop_threshold': 0.30,  # drop if >30% rows removed
}


def apply_sample_level_qc(df):
    """
    Apply hard removals at sample level: PM2.5 < 0 or > 500.
    
    Returns:
        df_clean: DataFrame with invalid samples removed
        removed_mask: Boolean mask of removed rows (aligned with input df index)
        stats: Dictionary with removal statistics
    """
    initial_count = len(df)
    
    # Hard removals
    invalid_mask = (
        (df['pm2_5_atm'] < QC_CONFIG['pm25_min']) |
        (df['pm2_5_atm'] > QC_CONFIG['pm25_max']) |
        df['pm2_5_atm'].isna()
    )
    
    df_clean = df[~invalid_mask].copy()
    removed_count = invalid_mask.sum()
    
    stats = {
        'initial_samples': initial_count,
        'removed_samples': removed_count,
        'removed_pct': (removed_count / initial_count * 100) if initial_count > 0 else 0,
        'reason': 'pm25_out_of_range'
    }
    
    return df_clean, invalid_mask, stats


def detect_spikes_stage1(df):
    """
    Stage 1: Auto-remove single-point blowups that return to baseline.
    
    Returns:
        df_clean: DataFrame with spikes removed
        removed_mask: Boolean mask of removed rows
        stats: Dictionary with removal statistics
    """
    df = df.copy()
    df = df.sort_values(['sensor_id', 'time_stamp']).reset_index(drop=True)
    
    removed_mask = pd.Series(False, index=df.index)
    spike_count = 0
    
    for sensor_id in df['sensor_id'].unique():
        sensor_df = df[df['sensor_id'] == sensor_id].copy()
        sensor_df = sensor_df.sort_values('time_stamp').reset_index(drop=True)
        
        if len(sensor_df) < 3:  # Need at least 3 readings
            continue
        
        for i in range(1, len(sensor_df) - 1):
            pm_current = sensor_df.iloc[i]['pm2_5_atm']
            pm_prev = sensor_df.iloc[i-1]['pm2_5_atm']
            
            # Check if spike condition met
            if (pm_current > QC_CONFIG['spike_multiplier'] * pm_prev and 
                pm_current > QC_CONFIG['spike_min_value']):
                
                # Check if returns to baseline within next 1-2 readings
                baseline_value = pm_prev
                threshold_low = baseline_value * (1 - QC_CONFIG['spike_return_threshold'])
                threshold_high = baseline_value * (1 + QC_CONFIG['spike_return_threshold'])
                
                # Check next readings
                return_to_baseline = False
                check_end = min(i + QC_CONFIG['spike_check_window'] + 1, len(sensor_df))
                
                for j in range(i + 1, check_end):
                    pm_next = sensor_df.iloc[j]['pm2_5_atm']
                    if threshold_low <= pm_next <= threshold_high:
                        return_to_baseline = True
                        break
                
                # If at end of series, don't auto-remove (just flag)
                if i + QC_CONFIG['spike_check_window'] >= len(sensor_df):
                    continue  # Don't auto-remove, will be flagged in Stage 2
                
                # Auto-remove if returns to baseline
                if return_to_baseline:
                    original_idx = sensor_df.iloc[i].name
                    removed_mask.loc[original_idx] = True
                    spike_count += 1
    
    df_clean = df[~removed_mask].copy()
    
    stats = {
        'removed_samples': removed_mask.sum(),
        'removed_pct': (removed_mask.sum() / len(df) * 100) if len(df) > 0 else 0,
        'reason': 'spike_stage1_auto_removed'
    }
    
    return df_clean, removed_mask, stats


def flag_spikes_stage2(df):
    """
    Stage 2: Flag suspicious spikes but keep them.
    
    Returns:
        flagged_df: DataFrame with spike_flag column
        stats: Dictionary with flagging statistics
    """
    df = df.copy()
    df = df.sort_values(['sensor_id', 'time_stamp']).reset_index(drop=True)
    df['spike_flag'] = False
    
    flagged_count = 0
    
    for sensor_id in df['sensor_id'].unique():
        sensor_df = df[df['sensor_id'] == sensor_id].copy()
        sensor_df = sensor_df.sort_values('time_stamp').reset_index(drop=True)
        
        if len(sensor_df) < 2:
            continue
        
        for i in range(1, len(sensor_df)):
            pm_current = sensor_df.iloc[i]['pm2_5_atm']
            pm_prev = sensor_df.iloc[i-1]['pm2_5_atm']
            
            # Flag if spike condition met
            if (pm_current > QC_CONFIG['spike_flag_multiplier'] * pm_prev and 
                pm_current > QC_CONFIG['spike_flag_min_value']):
                
                original_idx = sensor_df.iloc[i].name
                df.loc[original_idx, 'spike_flag'] = True
                flagged_count += 1
    
    stats = {
        'flagged_samples': flagged_count,
        'flagged_pct': (flagged_count / len(df) * 100) if len(df) > 0 else 0,
        'reason': 'spike_stage2_flagged'
    }
    
    return df, stats


def detect_stuck_sensors(df):
    """
    Detect and remove stuck sensor segments.
    
    Returns:
        df_clean: DataFrame with stuck segments removed
        removed_mask: Boolean mask of removed rows
        stats: Dictionary with removal statistics
    """
    df = df.copy()
    df = df.sort_values(['sensor_id', 'time_stamp']).reset_index(drop=True)
    
    removed_mask = pd.Series(False, index=df.index)
    stuck_segments = []
    
    window_readings = QC_CONFIG['stuck_window_hours'] * 2  # 30-min intervals
    identical_readings = QC_CONFIG['stuck_identical_hours'] * 2
    
    for sensor_id in df['sensor_id'].unique():
        sensor_df = df[df['sensor_id'] == sensor_id].copy()
        sensor_df = sensor_df.sort_values('time_stamp').reset_index(drop=True)
        
        if len(sensor_df) < window_readings:
            continue
        
        # Check for stuck segments
        for i in range(len(sensor_df) - window_readings + 1):
            window = sensor_df.iloc[i:i+window_readings]
            pm_values = window['pm2_5_atm'].values
            
            # Check variance and range
            std_val = np.std(pm_values)
            range_val = np.max(pm_values) - np.min(pm_values)
            
            is_stuck = (std_val < QC_CONFIG['stuck_std_threshold'] and 
                       range_val < QC_CONFIG['stuck_range_threshold'])
            
            # Also check for identical readings
            if not is_stuck and i + identical_readings <= len(sensor_df):
                identical_window = sensor_df.iloc[i:i+identical_readings]
                pm_rounded = np.round(identical_window['pm2_5_atm'].values, 1)
                if len(np.unique(pm_rounded)) == 1:
                    is_stuck = True
            
            if is_stuck:
                # Mark this segment for removal
                original_indices = window.index
                removed_mask.loc[original_indices] = True
                stuck_segments.append({
                    'sensor_id': sensor_id,
                    'start': window.iloc[0]['time_stamp'],
                    'end': window.iloc[-1]['time_stamp'],
                    'value': np.mean(pm_values)
                })
    
    df_clean = df[~removed_mask].copy()
    
    stats = {
        'removed_samples': removed_mask.sum(),
        'removed_pct': (removed_mask.sum() / len(df) * 100) if len(df) > 0 else 0,
        'stuck_segments': len(stuck_segments),
        'reason': 'stuck_sensor_segment'
    }
    
    return df_clean, removed_mask, stats, stuck_segments


def apply_coverage_thresholds(df):
    """
    Apply sensor-level coverage thresholds.
    Keep sensor if: total_samples >= 1000 AND (coverage_days >= 90 OR total_samples >= 5000)
    
    Returns:
        df_clean: DataFrame with low-coverage sensors removed
        dropped_sensors: List of dropped sensor IDs
        stats: Dictionary with removal statistics
    """
    sensor_stats = df.groupby('sensor_id').agg({
        'time_stamp': ['min', 'max', 'count'],
        'pm2_5_atm': 'count'
    }).reset_index()
    sensor_stats.columns = ['sensor_id', 'first_date', 'last_date', 'total_readings', 'pm25_count']
    sensor_stats['coverage_days'] = (sensor_stats['last_date'] - sensor_stats['first_date']).dt.days
    
    # Apply coverage rule
    keep_mask = (
        (sensor_stats['total_readings'] >= QC_CONFIG['min_samples']) &
        (
            (sensor_stats['coverage_days'] >= QC_CONFIG['min_coverage_days']) |
            (sensor_stats['total_readings'] >= QC_CONFIG['min_samples_alt'])
        )
    )
    
    kept_sensors = sensor_stats[keep_mask]['sensor_id'].tolist()
    dropped_sensors = sensor_stats[~keep_mask]['sensor_id'].tolist()
    
    df_clean = df[df['sensor_id'].isin(kept_sensors)].copy()
    
    stats = {
        'initial_sensors': len(sensor_stats),
        'kept_sensors': len(kept_sensors),
        'dropped_sensors': len(dropped_sensors),
        'dropped_sensor_ids': dropped_sensors,
        'initial_samples': len(df),
        'final_samples': len(df_clean),
        'removed_samples': len(df) - len(df_clean),
        'removed_pct': ((len(df) - len(df_clean)) / len(df) * 100) if len(df) > 0 else 0,
        'reason': 'coverage_threshold'
    }
    
    return df_clean, dropped_sensors, stats


def check_sensor_drop_threshold(df, qc_removed_by_sensor):
    """
    Drop entire sensors if >30% of rows removed from QC.
    
    Returns:
        df_clean: DataFrame with high-removal sensors dropped
        dropped_sensors: List of dropped sensor IDs
        stats: Dictionary with removal statistics
    """
    sensor_drops = []
    
    for sensor_id in df['sensor_id'].unique():
        sensor_df = df[df['sensor_id'] == sensor_id]
        total_samples = len(sensor_df)
        removed_samples = qc_removed_by_sensor.get(sensor_id, 0)
        
        removal_pct = (removed_samples / total_samples * 100) if total_samples > 0 else 0
        
        if removal_pct > (QC_CONFIG['sensor_drop_threshold'] * 100):
            sensor_drops.append({
                'sensor_id': sensor_id,
                'total_samples': total_samples,
                'removed_samples': removed_samples,
                'removal_pct': removal_pct
            })
    
    dropped_sensor_ids = [s['sensor_id'] for s in sensor_drops]
    df_clean = df[~df['sensor_id'].isin(dropped_sensor_ids)].copy()
    
    stats = {
        'dropped_sensors': len(dropped_sensor_ids),
        'dropped_sensor_ids': dropped_sensor_ids,
        'initial_samples': len(df),
        'final_samples': len(df_clean),
        'removed_samples': len(df) - len(df_clean),
        'removed_pct': ((len(df) - len(df_clean)) / len(df) * 100) if len(df) > 0 else 0,
        'reason': 'sensor_drop_threshold',
        'sensor_drop_details': sensor_drops
    }
    
    return df_clean, dropped_sensor_ids, stats


def run_qc_pipeline(df):
    """
    Run complete QC pipeline.
    
    Returns:
        df_clean: Cleaned DataFrame
        qc_report: Dictionary with QC statistics
    """
    print("="*70)
    print("RUNNING QUALITY CONTROL PIPELINE")
    print("="*70)
    
    initial_count = len(df)
    initial_sensors = df['sensor_id'].nunique()
    
    qc_report = {
        'config': QC_CONFIG,
        'initial_stats': {
            'total_samples': initial_count,
            'total_sensors': initial_sensors
        },
        'steps': []
    }
    
    # Step 1: Sample-level hard removals
    print("\n[Step 1] Sample-level hard removals (PM2.5 < 0 or > 500)...")
    df, removed_mask_1, stats_1 = apply_sample_level_qc(df)
    qc_report['steps'].append(stats_1)
    print(f"  Removed {stats_1['removed_samples']:,} samples ({stats_1['removed_pct']:.2f}%)")
    
    # Track removals by sensor (before filtering)
    qc_removed_by_sensor = {}
    removed_df = df[removed_mask_1]
    for sensor_id in removed_df['sensor_id'].unique():
        sensor_removed = (removed_df['sensor_id'] == sensor_id).sum()
        qc_removed_by_sensor[sensor_id] = qc_removed_by_sensor.get(sensor_id, 0) + sensor_removed
    df = df[~removed_mask_1].copy()
    
    # Step 2: Spike detection Stage 1 (auto-remove)
    print("\n[Step 2] Spike detection Stage 1 (auto-remove single-point blowups)...")
    df, removed_mask_2, stats_2 = detect_spikes_stage1(df)
    qc_report['steps'].append(stats_2)
    print(f"  Removed {stats_2['removed_samples']:,} samples ({stats_2['removed_pct']:.2f}%)")
    
    # Update removal tracking
    removed_df = df[removed_mask_2]
    for sensor_id in removed_df['sensor_id'].unique():
        sensor_removed = (removed_df['sensor_id'] == sensor_id).sum()
        qc_removed_by_sensor[sensor_id] = qc_removed_by_sensor.get(sensor_id, 0) + sensor_removed
    df = df[~removed_mask_2].copy()
    
    # Step 3: Spike detection Stage 2 (flag-only)
    print("\n[Step 3] Spike detection Stage 2 (flag suspicious spikes)...")
    df, stats_3 = flag_spikes_stage2(df)
    qc_report['steps'].append(stats_3)
    print(f"  Flagged {stats_3['flagged_samples']:,} samples ({stats_3['flagged_pct']:.2f}%)")
    
    # Step 4: Stuck sensor detection
    print("\n[Step 4] Stuck sensor detection (segment-level)...")
    df, removed_mask_4, stats_4, stuck_segments = detect_stuck_sensors(df)
    qc_report['steps'].append(stats_4)
    qc_report['stuck_segments'] = stuck_segments
    print(f"  Removed {stats_4['removed_samples']:,} samples ({stats_4['removed_pct']:.2f}%)")
    print(f"  Found {stats_4['stuck_segments']} stuck segments")
    
    # Update removal tracking
    removed_df = df[removed_mask_4]
    for sensor_id in removed_df['sensor_id'].unique():
        sensor_removed = (removed_df['sensor_id'] == sensor_id).sum()
        qc_removed_by_sensor[sensor_id] = qc_removed_by_sensor.get(sensor_id, 0) + sensor_removed
    df = df[~removed_mask_4].copy()
    
    # Step 5: Coverage thresholds
    print("\n[Step 5] Applying coverage thresholds...")
    df, dropped_sensors_5, stats_5 = apply_coverage_thresholds(df)
    qc_report['steps'].append(stats_5)
    print(f"  Kept {stats_5['kept_sensors']} sensors, dropped {stats_5['dropped_sensors']} sensors")
    print(f"  Removed {stats_5['removed_samples']:,} samples ({stats_5['removed_pct']:.2f}%)")
    
    # Step 6: Sensor drop threshold (>30% removed)
    print("\n[Step 6] Checking sensor drop threshold (>30% rows removed)...")
    df, dropped_sensors_6, stats_6 = check_sensor_drop_threshold(df, qc_removed_by_sensor)
    qc_report['steps'].append(stats_6)
    if stats_6['dropped_sensors'] > 0:
        print(f"  Dropped {stats_6['dropped_sensors']} sensors with >30% removal")
        print(f"  Removed {stats_6['removed_samples']:,} samples ({stats_6['removed_pct']:.2f}%)")
    else:
        print("  No sensors exceeded drop threshold")
    
    # Final summary
    final_count = len(df)
    final_sensors = df['sensor_id'].nunique()
    
    qc_report['final_stats'] = {
        'total_samples': final_count,
        'total_sensors': final_sensors,
        'samples_removed': initial_count - final_count,
        'samples_removed_pct': ((initial_count - final_count) / initial_count * 100) if initial_count > 0 else 0,
        'sensors_removed': initial_sensors - final_sensors,
        'sensors_removed_pct': ((initial_sensors - final_sensors) / initial_sensors * 100) if initial_sensors > 0 else 0
    }
    
    print(f"\n{'='*70}")
    print("QC PIPELINE COMPLETE")
    print(f"{'='*70}")
    print(f"Initial: {initial_count:,} samples, {initial_sensors} sensors")
    print(f"Final:   {final_count:,} samples, {final_sensors} sensors")
    print(f"Removed: {initial_count - final_count:,} samples ({(initial_count - final_count) / initial_count * 100:.2f}%)")
    print(f"Dropped: {initial_sensors - final_sensors} sensors")
    
    # Check if dataset is still usable
    if final_sensors < 20:
        print(f"\n⚠️  WARNING: Only {final_sensors} sensors retained (< 20 minimum)")
        print("   Dataset may be unreliable for training")
    else:
        print(f"\n✓ Dataset is usable: {final_sensors} sensors retained")
    
    return df, qc_report


def main():
    """Main execution function."""
    # Paths
    input_file = Path(__file__).parent.parent / "data" / "raw" / "purpleair_combined_raw.csv"
    output_dir = Path(__file__).parent.parent / "data" / "processed"
    qc_report_dir = Path(__file__).parent.parent / "qc_reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    qc_report_dir.mkdir(parents=True, exist_ok=True)
    
    print("="*70)
    print("PHASE 2: DATA QUALITY CONTROL")
    print("="*70)
    
    # Load raw data
    print(f"\nLoading raw data from: {input_file}")
    df = pd.read_csv(input_file, parse_dates=['time_stamp'])
    print(f"Loaded {len(df):,} rows")
    
    # Run QC pipeline
    df_clean, qc_report = run_qc_pipeline(df)
    
    # Save cleaned data
    output_file = output_dir / "purpleair_qc_cleaned.csv"
    df_clean.to_csv(output_file, index=False)
    print(f"\nCleaned data saved to: {output_file}")
    
    # Save QC report
    report_file = qc_report_dir / f"qc_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(qc_report, f, indent=2, default=str)
    print(f"QC report saved to: {report_file}")
    
    # Also save as readable text
    report_txt = qc_report_dir / f"qc_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_txt, 'w') as f:
        f.write("="*70 + "\n")
        f.write("QUALITY CONTROL REPORT\n")
        f.write("="*70 + "\n\n")
        f.write(f"Initial: {qc_report['initial_stats']['total_samples']:,} samples, {qc_report['initial_stats']['total_sensors']} sensors\n")
        f.write(f"Final:   {qc_report['final_stats']['total_samples']:,} samples, {qc_report['final_stats']['total_sensors']} sensors\n")
        f.write(f"Removed: {qc_report['final_stats']['samples_removed']:,} samples ({qc_report['final_stats']['samples_removed_pct']:.2f}%)\n")
        f.write(f"Dropped: {qc_report['final_stats']['sensors_removed']} sensors\n\n")
        f.write("QC Steps:\n")
        for i, step in enumerate(qc_report['steps'], 1):
            f.write(f"  Step {i}: {step.get('reason', 'unknown')}\n")
            if 'removed_samples' in step:
                f.write(f"    Removed: {step['removed_samples']:,} samples ({step.get('removed_pct', 0):.2f}%)\n")
            if 'flagged_samples' in step:
                f.write(f"    Flagged: {step['flagged_samples']:,} samples ({step.get('flagged_pct', 0):.2f}%)\n")
    
    print(f"QC report (text) saved to: {report_txt}")


if __name__ == "__main__":
    main()
