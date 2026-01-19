#!/usr/bin/env python3
"""Test cleaned addresses (business names removed)"""

addresses_cleaned = [
    "2523 Bishop Ave, Fremont, CA 94536",
    "39400 Paseo Padre Pkwy, Fremont, CA 94538",
    "4620 Mattos Dr, Fremont, CA 94536",
    "5400 Mowry Ave, Fremont, CA 94538",
    "36007 Pizarro Dr, Fremont, CA 94536",
    "3377 Alder Ave, Fremont, CA 94536",
    "34665 Allegheny Ct, Fremont, CA 94555",
    "1251 Peralta Blvd, Fremont, CA 94536",
    "40500 Paseo Padre Pkwy, Fremont, CA 94538",
    "41800 Blacow Rd, Fremont, CA 94538"
]

# Business names for reference
business_names = [
    "Little Flowers Day Care & Preschool",
    "Kaiser Permanente Fremont Medical Center",
    "Glenmoor Elementary School",
    "Best Western Plus Garden Court Inn",
    "Wonderland Preschool and Daycare",
    "Los Cerritos Community Center",
    "Crandall Creek Park",
    "Shinn Historical Park and Arboretum",
    "Palms Pavilion Picnic Area",
    "Irvington High School"
]

import subprocess
import sys
from pathlib import Path

API_KEY = "C258449D-E52B-11F0-B596-4201AC1DC123"
DATA_DIR = Path(__file__).parent
TEST_SCRIPT = DATA_DIR / "test_predictions.py"

results = {'success': [], 'failed': []}

print("="*80)
print("TESTING CLEANED ADDRESSES (business names removed)")
print("="*80)

for i, (addr, business) in enumerate(zip(addresses_cleaned, business_names), 1):
    print(f"\n{i}/10: {business}")
    print(f"  Address: {addr}")
    
    try:
        cmd = [sys.executable, str(TEST_SCRIPT), '--address', addr, '--api-key', API_KEY]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        
        if result.returncode == 0 and '1H Forecast' in result.stdout:
            print(f"  ✓ SUCCESS")
            results['success'].append({'business': business, 'address': addr})
        else:
            print(f"  ✗ FAILED")
            print(f"    {result.stderr[:200]}")
            results['failed'].append({'business': business, 'address': addr, 'error': result.stderr[:300]})
    except Exception as e:
        print(f"  ✗ EXCEPTION: {e}")
        results['failed'].append({'business': business, 'address': addr, 'error': str(e)})

print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")
print(f"Successful: {len(results['success'])}/10")
print(f"Failed: {len(results['failed'])}/10")

if results['success']:
    print(f"\n✓ Working addresses:")
    for item in results['success']:
        print(f"  - {item['business']}: {item['address']}")

if results['failed']:
    print(f"\n✗ Failed addresses:")
    for item in results['failed']:
        print(f"  - {item['business']}: {item['address']}")
        if 'error' in item:
            print(f"    Error: {item['error'][:150]}")

print(f"\n{'='*80}")
if len(results['success']) == 10:
    print("✓ ALL ADDRESSES WORKING!")
    print("\nFor validation study, use cleaned addresses (business names removed)")
else:
    print(f"⚠ {len(results['failed'])} addresses need attention")
print(f"{'='*80}")
