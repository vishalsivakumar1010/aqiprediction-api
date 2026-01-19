#!/usr/bin/env python3
"""
Simplified Validation Study Runner
Runs forecasts for multiple addresses and compares with actuals.

Usage example:
    python run_validation.py --addresses "addr1,addr2,..." --api-key YOUR_KEY --hours 12
"""

import subprocess
import sys
import time
import json
from datetime import datetime, timedelta
from pathlib import Path

def run_validation(addresses_list, api_key, hours=12, data_dir=None, model_dir=None):
    """
    Run validation study by calling test_predictions.py for each address every hour.
    
    Args:
        addresses_list: List of addresses
        api_key: PurpleAir API key
        hours: Number of hours to run
        data_dir: Data directory (defaults to script location)
        model_dir: Model directory (defaults to data_dir/models)
    """
    if data_dir is None:
        data_dir = Path(__file__).parent
    if model_dir is None:
        model_dir = data_dir / 'models'
    
    results_dir = data_dir / 'validation_results'
    results_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_file = results_dir / f'validation_results_{timestamp}.jsonl'
    summary_file = results_dir / f'validation_summary_{timestamp}.txt'
    
    print(f"="*70)
    print(f"VALIDATION STUDY")
    print(f"="*70)
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration: {hours} hours")
    print(f"Addresses: {len(addresses_list)}")
    print(f"Results will be saved to: {results_dir}")
    print(f"="*70)
    
    all_results = []
    start_time = datetime.now()
    
    for round_num in range(1, hours + 1):
        print(f"\n{'='*70}")
        print(f"ROUND {round_num}/{hours} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        
        round_results = {
            'round': round_num,
            'timestamp': datetime.now().isoformat(),
            'addresses': {}
        }
        
        for addr in addresses_list:
            print(f"\n{addr}:")
            try:
                # Call test_predictions.py as subprocess to capture output
                cmd = [
                    sys.executable,
                    str(data_dir / 'test_predictions.py'),
                    '--address', addr,
                    '--api-key', api_key
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120  # 2 minute timeout per address
                )
                
                # Parse output to extract predictions
                output = result.stdout
                if result.returncode == 0:
                    # Extract key values from output
                    # This is a simple parser - you might want to improve it
                    lines = output.split('\n')
                    current_pm25 = None
                    forecast_1h_pm25 = None
                    forecast_3h_pm25 = None
                    
                    for line in lines:
                        if 'Current LIVE Conditions' in line or 'PM2.5:' in line:
                            # Try to extract PM2.5 value
                            if 'PM2.5:' in line:
                                try:
                                    parts = line.split('PM2.5:')
                                    if len(parts) > 1:
                                        val = float(parts[1].split()[0])
                                        if current_pm25 is None:
                                            current_pm25 = val
                                except:
                                    pass
                        elif '1H Forecast' in line or 'Predicted PM2.5:' in line:
                            if 'Predicted PM2.5:' in line:
                                try:
                                    forecast_1h_pm25 = float(line.split('Predicted PM2.5:')[1].split()[0])
                                except:
                                    pass
                        elif '3H Forecast' in line:
                            if 'Predicted PM2.5:' in line:
                                try:
                                    forecast_3h_pm25 = float(line.split('Predicted PM2.5:')[1].split()[0])
                                except:
                                    pass
                    
                    round_results['addresses'][addr] = {
                        'success': True,
                        'current_pm25': current_pm25,
                        'forecast_1h_pm25': forecast_1h_pm25,
                        'forecast_3h_pm25': forecast_3h_pm25,
                        'raw_output': output[:500]  # Store first 500 chars
                    }
                    print(f"  ✓ Current: {current_pm25}, 1h: {forecast_1h_pm25}, 3h: {forecast_3h_pm25}")
                else:
                    round_results['addresses'][addr] = {
                        'success': False,
                        'error': result.stderr[:200]
                    }
                    print(f"  ✗ Error: {result.stderr[:100]}")
                    
            except Exception as e:
                round_results['addresses'][addr] = {
                    'success': False,
                    'error': str(e)
                }
                print(f"  ✗ Exception: {e}")
        
        # Save results incrementally
        all_results.append(round_results)
        with open(results_file, 'a') as f:
            f.write(json.dumps(round_results) + '\n')
        
        # Wait for next round (if not last)
        if round_num < hours:
            wait_until = start_time + timedelta(hours=round_num)
            wait_seconds = (wait_until - datetime.now()).total_seconds()
            if wait_seconds > 0:
                print(f"\nWaiting {wait_seconds/60:.1f} minutes until next round...")
                time.sleep(wait_seconds)
            else:
                print(f"\n⚠ Running late, proceeding immediately...")
    
    # Generate summary
    print(f"\n{'='*70}")
    print("VALIDATION STUDY COMPLETE")
    print(f"{'='*70}")
    
    with open(summary_file, 'w') as f:
        f.write("VALIDATION STUDY SUMMARY\n")
        f.write("="*70 + "\n")
        f.write(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total rounds: {len(all_results)}\n")
        f.write(f"Addresses: {len(addresses_list)}\n\n")
        
        for round_data in all_results:
            f.write(f"\nRound {round_data['round']} ({round_data['timestamp']}):\n")
            for addr, data in round_data['addresses'].items():
                if data.get('success'):
                    f.write(f"  {addr}:\n")
                    f.write(f"    Current: {data.get('current_pm25', 'N/A')}\n")
                    f.write(f"    1h Forecast: {data.get('forecast_1h_pm25', 'N/A')}\n")
                    f.write(f"    3h Forecast: {data.get('forecast_3h_pm25', 'N/A')}\n")
                else:
                    f.write(f"  {addr}: ERROR - {data.get('error', 'Unknown')}\n")
    
    print(f"\n✓ Results saved to:")
    print(f"  - {results_file}")
    print(f"  - {summary_file}")
    print(f"\nNext steps:")
    print(f"  1. Wait for forecast times to pass")
    print(f"  2. Run comparison script to fetch actuals and calculate errors")
    print(f"  3. Analyze results")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Run validation study')
    parser.add_argument('--addresses', required=True, help='Comma-separated addresses')
    parser.add_argument('--api-key', required=True, help='PurpleAir API key')
    parser.add_argument('--hours', type=int, default=12, help='Number of hours')
    parser.add_argument('--data-dir', help='Data directory')
    parser.add_argument('--model-dir', help='Model directory')
    
    args = parser.parse_args()
    
    addresses = [a.strip() for a in args.addresses.split(',')]
    
    run_validation(
        addresses_list=addresses,
        api_key=args.api_key,
        hours=args.hours,
        data_dir=args.data_dir,
        model_dir=args.model_dir
    )
