#!/usr/bin/env python3
"""
Test All Validation Addresses with New Models (Open-Meteo)
Also fetch and display Open-Meteo current data for Fremont
"""

import subprocess
import sys
import os
import requests
from datetime import datetime
import pandas as pd

# Fremont coordinates
FREMONT_LAT = 37.5483
FREMONT_LON = -121.9886

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

api_key = 'C258449D-E52B-11F0-B596-4201AC1DC123'

def fetch_openmeteo_current(latitude, longitude):
    """Fetch current weather data from Open-Meteo for a location."""
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "wind_direction_10m,wind_speed_10m,pm2_5",
            "forecast_days": 1,
            "timezone": "America/Los_Angeles"
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "hourly" not in data:
            return None
        
        hourly = data["hourly"]
        
        # Get current hour data (first hour of forecast)
        if len(hourly["time"]) > 0:
            current_time = hourly["time"][0]
            current_wdir = hourly.get("wind_direction_10m", [None])[0]
            current_wspd = hourly.get("wind_speed_10m", [None])[0]
            current_pm25 = hourly.get("pm2_5", [None])[0]
            
            return {
                "time": current_time,
                "wind_direction_10m": current_wdir,
                "wind_speed_10m": current_wspd,
                "pm2_5": current_pm25
            }
        return None
    except Exception as e:
        print(f"Error fetching Open-Meteo data: {e}")
        return None

def parse_prediction_output(output):
    """Parse test_predictions.py output to extract values."""
    lines = output.split('\n')
    
    result = {
        'current_pm25': None,
        'current_aqi': None,
        'current_category': None,
        'forecast_1h_pm25': None,
        'forecast_1h_aqi': None,
        'forecast_1h_category': None,
        'forecast_3h_pm25': None,
        'forecast_3h_aqi': None,
        'forecast_3h_category': None,
    }
    
    # Parse current values
    for i, line in enumerate(lines):
        if 'Current LIVE Conditions' in line or 'Most Recent Historical' in line:
            # Look for PM2.5, AQI in next few lines
            for j in range(i, min(len(lines), i+10)):
                if 'PM2.5:' in lines[j]:
                    try:
                        result['current_pm25'] = float(lines[j].split('PM2.5:')[1].split('μg')[0].strip())
                    except:
                        pass
                if 'AQI:' in lines[j] and 'Forecast' not in lines[j]:
                    try:
                        parts = lines[j].split('AQI:')[1].split('(')
                        result['current_aqi'] = int(parts[0].strip())
                        if len(parts) > 1:
                            result['current_category'] = parts[1].split(')')[0].strip()
                    except:
                        pass
        
        # Parse 1H forecast
        if '1H Forecast:' in line or '1-hour Forecast:' in line or '1H Forecast' in line:
            for j in range(i, min(len(lines), i+5)):
                if 'PM2.5:' in lines[j] or 'Predicted PM2.5:' in lines[j]:
                    try:
                        text = lines[j].split('PM2.5:')[-1].split('μg')[0].strip()
                        result['forecast_1h_pm25'] = float(text)
                    except:
                        pass
                if 'AQI:' in lines[j] or 'Predicted AQI:' in lines[j]:
                    try:
                        parts = lines[j].split('AQI:')[-1].split('(')
                        result['forecast_1h_aqi'] = int(parts[0].strip())
                        if len(parts) > 1:
                            result['forecast_1h_category'] = parts[1].split(')')[0].strip()
                    except:
                        pass
        
        # Parse 3H forecast
        if '3H Forecast:' in line or '3-hour Forecast:' in line or '3H Forecast' in line:
            for j in range(i, min(len(lines), i+5)):
                if 'PM2.5:' in lines[j] or 'Predicted PM2.5:' in lines[j]:
                    try:
                        text = lines[j].split('PM2.5:')[-1].split('μg')[0].strip()
                        result['forecast_3h_pm25'] = float(text)
                    except:
                        pass
                if 'AQI:' in lines[j] or 'Predicted AQI:' in lines[j]:
                    try:
                        parts = lines[j].split('AQI:')[-1].split('(')
                        result['forecast_3h_aqi'] = int(parts[0].strip())
                        if len(parts) > 1:
                            result['forecast_3h_category'] = parts[1].split(')')[0].strip()
                    except:
                        pass
    
    return result

print("="*80)
print("TESTING ALL VALIDATION ADDRESSES WITH NEW MODELS (OPEN-METEO)")
print("="*80)
print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# Fetch Open-Meteo current data for Fremont
print("="*80)
print("OPEN-METEO CURRENT DATA FOR FREMONT")
print("="*80)
print(f"Location: ({FREMONT_LAT}, {FREMONT_LON})")
print(f"Fetching current data from Open-Meteo...")

openmeteo_data = fetch_openmeteo_current(FREMONT_LAT, FREMONT_LON)

if openmeteo_data:
    print(f"\n✓ Open-Meteo Current Data (Fremont):")
    print(f"  Time: {openmeteo_data.get('time', 'N/A')}")
    if openmeteo_data.get('wind_direction_10m') is not None:
        print(f"  Wind Direction: {openmeteo_data['wind_direction_10m']:.0f}°")
    if openmeteo_data.get('wind_speed_10m') is not None:
        print(f"  Wind Speed: {openmeteo_data['wind_speed_10m']:.2f} km/h")
    if openmeteo_data.get('pm2_5') is not None:
        print(f"  PM2.5: {openmeteo_data['pm2_5']:.2f} μg/m³")
    else:
        print(f"  PM2.5: Not available (Open-Meteo forecast API)")
else:
    print(f"\n⚠ Could not fetch Open-Meteo current data")

print("\n" + "="*80)
print("TESTING ALL ADDRESSES")
print("="*80)
print()

results = []

for i, address in enumerate(addresses, 1):
    print(f"\n{'='*80}")
    print(f"Address {i}/{len(addresses)}: {address}")
    print(f"{'='*80}")
    
    try:
        result = subprocess.run(
            ['python3', 'test_predictions.py', '--address', address, '--api-key', api_key],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # Parse output
        parsed = parse_prediction_output(result.stdout)
        
        result_data = {
            'address': address,
            'success': result.returncode == 0,
            **parsed
        }
        
        results.append(result_data)
        
        # Print summary
        print(f"\nCurrent Conditions:")
        if result_data['current_pm25'] is not None:
            print(f"  PM2.5: {result_data['current_pm25']:.1f} μg/m³")
        if result_data['current_aqi'] is not None:
            print(f"  AQI: {result_data['current_aqi']} ({result_data.get('current_category', 'N/A')})")
        
        print(f"\nForecasts:")
        if result_data['forecast_1h_pm25'] is not None:
            print(f"  1h: PM2.5 {result_data['forecast_1h_pm25']:.1f} μg/m³, AQI {result_data.get('forecast_1h_aqi', 'N/A')} ({result_data.get('forecast_1h_category', 'N/A')})")
        if result_data['forecast_3h_pm25'] is not None:
            print(f"  3h: PM2.5 {result_data['forecast_3h_pm25']:.1f} μg/m³, AQI {result_data.get('forecast_3h_aqi', 'N/A')} ({result_data.get('forecast_3h_category', 'N/A')})")
        
        if result.stderr:
            print(f"\n⚠ Warnings/Errors (stderr):")
            print(result.stderr[:500])  # First 500 chars
        
    except subprocess.TimeoutExpired:
        print(f"⚠ Timeout: Address took too long")
        results.append({'address': address, 'success': False, 'error': 'Timeout'})
    except Exception as e:
        print(f"✗ Error: {e}")
        results.append({'address': address, 'success': False, 'error': str(e)})

# Summary
print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Successfully tested: {sum(1 for r in results if r.get('success'))}/{len(addresses)}")
print()

# Create DataFrame for better formatting
summary_data = []
for r in results:
    if r.get('success'):
        summary_data.append({
            'Address': r['address'],
            'Current PM2.5': f"{r.get('current_pm25', 'N/A'):.1f}" if r.get('current_pm25') is not None else 'N/A',
            'Current AQI': r.get('current_aqi', 'N/A'),
            '1h PM2.5': f"{r.get('forecast_1h_pm25', 'N/A'):.1f}" if r.get('forecast_1h_pm25') is not None else 'N/A',
            '1h AQI': r.get('forecast_1h_aqi', 'N/A'),
            '3h PM2.5': f"{r.get('forecast_3h_pm25', 'N/A'):.1f}" if r.get('forecast_3h_pm25') is not None else 'N/A',
            '3h AQI': r.get('forecast_3h_aqi', 'N/A'),
        })

if summary_data:
    df = pd.DataFrame(summary_data)
    print("\nResults Table:")
    print(df.to_string(index=False))
    
    # Save to CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'test_all_addresses_openmeteo_{timestamp}.csv'
    df.to_csv(output_file, index=False)
    print(f"\n✓ Results saved to: {output_file}")

print("\n" + "="*80)
print("OPEN-METEO CURRENT DATA FOR FREMONT (Summary)")
print("="*80)
if openmeteo_data:
    print(f"Time: {openmeteo_data.get('time', 'N/A')}")
    if openmeteo_data.get('wind_direction_10m') is not None:
        print(f"Wind Direction: {openmeteo_data['wind_direction_10m']:.0f}°")
    if openmeteo_data.get('wind_speed_10m') is not None:
        print(f"Wind Speed: {openmeteo_data['wind_speed_10m']:.2f} km/h ({openmeteo_data['wind_speed_10m']*0.621371:.2f} mph)")
    if openmeteo_data.get('pm2_5') is not None:
        print(f"PM2.5: {openmeteo_data['pm2_5']:.2f} μg/m³")
    else:
        print(f"PM2.5: Not available in Open-Meteo forecast API")
else:
    print("Could not fetch Open-Meteo data")

print("\n" + "="*80)
print("TESTING COMPLETE")
print("="*80)
