#!/usr/bin/env python3
"""
Quick test script to verify all addresses work before running full validation study.
"""

import subprocess
import sys
from pathlib import Path

# List of addresses to test
addresses = [
    "Little Flowers Day Care & Preschool 2523 Bishop Ave, Fremont, CA 94536",
    "Kaiser Permanente Fremont Medical Center 39400 Paseo Padre Pkwy, Fremont, CA 94538",
    "Glenmoor Elementary School 4620 Mattos Dr, Fremont, CA 94536",
    "Best Western Plus Garden Court Inn 5400 Mowry Ave, Fremont, CA 94538",
    "Wonderland Preschool and Daycare 36007 Pizarro Dr, Fremont, CA 94536",
    "Los Cerritos Community Center 3377 Alder Ave, Fremont, CA 94536",
    "Crandall Creek Park 34665 Allegheny Ct, Fremont, CA 94555",
    "Shinn Historical Park and Arboretum 1251 Peralta Blvd, Fremont, CA 94536",
    "Palms Pavilion Picnic Area 40500 Paseo Padre Pkwy, Fremont, CA 94538",
    "Irvington High School 41800 Blacow Rd, Fremont, CA 94538"
]

API_KEY = "C258449D-E52B-11F0-B596-4201AC1DC123"
DATA_DIR = Path(__file__).parent
TEST_SCRIPT = DATA_DIR / "test_predictions.py"

results = {
    'success': [],
    'failed': []
}

print("="*80)
print("TESTING ALL 10 ADDRESSES")
print("="*80)
print(f"Total addresses: {len(addresses)}\n")

for i, addr in enumerate(addresses, 1):
    print(f"\n{'='*80}")
    print(f"TEST {i}/10: {addr}")
    print(f"{'='*80}")
    
    try:
        cmd = [
            sys.executable,
            str(TEST_SCRIPT),
            '--address', addr,
            '--api-key', API_KEY
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180  # 3 minute timeout
        )
        
        if result.returncode == 0:
            # Check if we got predictions
            output = result.stdout
            if '1H Forecast' in output and '3H Forecast' in output:
                # Extract key info
                lines = output.split('\n')
                sensor_found = False
                predictions_found = False
                
                for line in lines:
                    if 'Nearest Sensor Found' in line or 'Sensor ID:' in line:
                        sensor_found = True
                    if 'Predicted PM2.5:' in line or 'Forecast' in line:
                        predictions_found = True
                
                if sensor_found and predictions_found:
                    print(f"✓ SUCCESS - Sensor found and predictions generated")
                    results['success'].append({
                        'address': addr,
                        'output': output[:500]  # Store first 500 chars
                    })
                else:
                    print(f"⚠ PARTIAL - Script ran but may have issues")
                    print(f"  Sensor found: {sensor_found}, Predictions: {predictions_found}")
                    results['failed'].append({
                        'address': addr,
                        'reason': 'Missing expected output',
                        'output': output[:1000]
                    })
            else:
                print(f"✗ FAILED - No forecasts in output")
                results['failed'].append({
                    'address': addr,
                    'reason': 'No forecasts found',
                    'output': output[:1000],
                    'stderr': result.stderr[:500]
                })
        else:
            print(f"✗ FAILED - Script returned error code {result.returncode}")
            print(f"  Error: {result.stderr[:300]}")
            results['failed'].append({
                'address': addr,
                'reason': f'Exit code {result.returncode}',
                'stderr': result.stderr[:1000],
                'stdout': result.stdout[:500]
            })
            
    except subprocess.TimeoutExpired:
        print(f"✗ FAILED - Timeout after 3 minutes")
        results['failed'].append({
            'address': addr,
            'reason': 'Timeout',
        })
    except Exception as e:
        print(f"✗ FAILED - Exception: {e}")
        results['failed'].append({
            'address': addr,
            'reason': str(e)
        })

# Summary
print(f"\n{'='*80}")
print("TEST SUMMARY")
print(f"{'='*80}")
print(f"Total tested: {len(addresses)}")
print(f"Successful: {len(results['success'])}")
print(f"Failed: {len(results['failed'])}")

if results['success']:
    print(f"\n✓ Successful addresses:")
    for item in results['success']:
        print(f"  - {item['address']}")

if results['failed']:
    print(f"\n✗ Failed addresses:")
    for item in results['failed']:
        print(f"  - {item['address']}: {item['reason']}")
        if 'stderr' in item:
            print(f"    Error details: {item['stderr'][:200]}")

print(f"\n{'='*80}")
if len(results['success']) == len(addresses):
    print("✓ ALL ADDRESSES WORKING - Ready for validation study!")
else:
    print(f"⚠ {len(results['failed'])} ADDRESS(ES) NEED ATTENTION")
    print("  Review failed addresses before running full validation study")
print(f"{'='*80}")
