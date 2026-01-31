"""
Phase 2: Step 1 - Fetch Sensor Locations from PurpleAir API
Fetches latitude/longitude for all sensors in the dataset.
"""

import requests
import pandas as pd
import os
import glob
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

# PurpleAir API key
API_KEY = "C258449D-E52B-11F0-B596-4201AC1DC123"


def get_sensor_ids_from_files(data_directory):
    """
    Extract sensor IDs from CSV filenames in the directory.
    
    Args:
        data_directory: Path to directory containing sensor CSV files
        
    Returns:
        List of sensor IDs
    """
    csv_files = glob.glob(os.path.join(data_directory, "*30-Minute Average.csv"))
    sensor_ids = []
    
    for file_path in csv_files:
        filename = os.path.basename(file_path)
        sensor_id = int(filename.split()[0])
        sensor_ids.append(sensor_id)
    
    return sorted(sensor_ids)


def fetch_sensor_info(api_key, sensor_ids):
    """
    Fetch sensor information including latitude and longitude from Purple Air API.
    
    Args:
        api_key: Purple Air API read key
        sensor_ids: List of sensor IDs
        
    Returns:
        DataFrame with sensor information
    """
    base_url = "https://api.purpleair.com/v1/sensors"
    headers = {
        'X-API-Key': api_key
    }
    
    sensor_data = []
    
    for sensor_id in sensor_ids:
        url = f"{base_url}/{sensor_id}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'sensor' not in data:
                print(f"Warning: No sensor data found for sensor {sensor_id}")
                continue
            
            sensor_info = data['sensor']
            
            # Extract relevant information
            sensor_record = {
                'sensor_id': sensor_id,
                'name': sensor_info.get('name', 'Unknown'),
                'latitude': sensor_info.get('latitude'),
                'longitude': sensor_info.get('longitude'),
                'altitude': sensor_info.get('altitude'),
                'location_type': sensor_info.get('location_type'),
                'model': sensor_info.get('model'),
                'hardware': sensor_info.get('hardware'),
                'date_created': sensor_info.get('date_created'),
            }
            
            sensor_data.append(sensor_record)
            print(f"✓ Fetched data for sensor {sensor_id}: {sensor_info.get('name', 'Unknown')}")
            print(f"  Location: ({sensor_record['latitude']}, {sensor_record['longitude']})")
            
        except requests.exceptions.RequestException as e:
            print(f"✗ Error fetching sensor {sensor_id}: {e}")
            continue
        except Exception as e:
            print(f"✗ Unexpected error for sensor {sensor_id}: {e}")
            continue
    
    if not sensor_data:
        raise ValueError("No sensor data was successfully fetched")
    
    df = pd.DataFrame(sensor_data)
    return df


def main():
    """Main execution function."""
    # Paths
    purpleair_dir = "/Users/vishalsivakumar/Library/Application Support/com.purpleair.data-download-tool/PurpleAir Download 1-25-2026-Fullset"
    output_dir = Path(__file__).parent.parent / "data" / "sensor_locations"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("="*70)
    print("PHASE 2: FETCHING SENSOR LOCATIONS FROM PURPLEAIR API")
    print("="*70)
    
    # Get sensor IDs from files
    print(f"\nScanning directory: {purpleair_dir}")
    sensor_ids = get_sensor_ids_from_files(purpleair_dir)
    
    print(f"\nFound {len(sensor_ids)} sensors:")
    for sid in sensor_ids[:10]:  # Show first 10
        print(f"  - {sid}")
    if len(sensor_ids) > 10:
        print(f"  ... and {len(sensor_ids) - 10} more")
    
    # Fetch sensor information
    print(f"\n{'='*70}")
    print("Fetching sensor information from PurpleAir API...")
    print(f"{'='*70}")
    sensor_df = fetch_sensor_info(API_KEY, sensor_ids)
    
    # Summary
    print(f"\n{'='*70}")
    print("SENSOR LOCATION SUMMARY")
    print(f"{'='*70}")
    print(f"\nTotal sensors fetched: {len(sensor_df)}")
    print(f"\nSensor Locations:")
    print("-"*70)
    print(sensor_df[['sensor_id', 'name', 'latitude', 'longitude']].to_string(index=False))
    
    # Geographic statistics
    if len(sensor_df) > 0:
        avg_lat = sensor_df['latitude'].mean()
        avg_lon = sensor_df['longitude'].mean()
        lat_range = sensor_df['latitude'].max() - sensor_df['latitude'].min()
        lon_range = sensor_df['longitude'].max() - sensor_df['longitude'].min()
        
        print(f"\nGeographic Statistics:")
        print(f"  Center: ({avg_lat:.6f}, {avg_lon:.6f})")
        print(f"  Latitude range: {lat_range:.6f} degrees")
        print(f"  Longitude range: {lon_range:.6f} degrees")
    
    # Save sensor locations
    csv_file = output_dir / "sensor_locations.csv"
    pkl_file = output_dir / "sensor_locations.pkl"
    
    sensor_df.to_csv(csv_file, index=False)
    sensor_df.to_pickle(pkl_file)
    
    print(f"\n{'='*70}")
    print("COMPLETE")
    print(f"{'='*70}")
    print(f"\nSensor locations saved to:")
    print(f"  CSV: {csv_file}")
    print(f"  PKL: {pkl_file}")


if __name__ == "__main__":
    main()
