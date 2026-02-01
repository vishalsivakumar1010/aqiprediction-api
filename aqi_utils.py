"""
AQI Calculation Utilities
Converts PM2.5 values to AQI and categories based on US EPA standards
"""

import numpy as np
import pandas as pd


def pm25_to_aqi(pm25):
    """
    Convert PM2.5 concentration (μg/m³) to AQI using US EPA formula.
    
    Args:
        pm25: PM2.5 concentration value(s) - can be scalar or array-like
        
    Returns:
        AQI value(s) of the same shape as input
    """
    pm25 = np.asarray(pm25)
    aqi = np.zeros_like(pm25, dtype=float)
    
    # AQI breakpoints for PM2.5 (US EPA standard)
    # Format: (C_low, C_high, I_low, I_high)
    breakpoints = [
        (0.0, 12.0, 0, 50),      # Good
        (12.1, 35.4, 51, 100),   # Moderate
        (35.5, 55.4, 101, 150),  # Unhealthy for Sensitive Groups
        (55.5, 150.4, 151, 200), # Unhealthy
        (150.5, 250.4, 201, 300), # Very Unhealthy
        (250.5, 500.4, 301, 500), # Hazardous
    ]
    
    for c_low, c_high, i_low, i_high in breakpoints:
        mask = (pm25 >= c_low) & (pm25 <= c_high)
        if np.any(mask):
            aqi[mask] = ((i_high - i_low) / (c_high - c_low)) * (pm25[mask] - c_low) + i_low
    
    # Handle values above 500.4 (extended hazardous)
    mask = pm25 > 500.4
    if np.any(mask):
        # Extrapolate beyond 500 AQI (though this is rare)
        aqi[mask] = 500 + ((pm25[mask] - 500.4) / 500.4) * 300  # Cap at 800
    
    return np.round(aqi).astype(int)


def aqi_to_category(aqi):
    """
    Convert AQI value to category string.
    
    Args:
        aqi: AQI value(s) - can be scalar or array-like
        
    Returns:
        Category string(s) of the same shape as input
    """
    aqi = np.asarray(aqi)
    categories = np.zeros_like(aqi, dtype=object)
    
    categories[aqi <= 50] = "Good"
    categories[(aqi >= 51) & (aqi <= 100)] = "Moderate"
    categories[(aqi >= 101) & (aqi <= 150)] = "Unhealthy for Sensitive Groups"
    categories[(aqi >= 151) & (aqi <= 200)] = "Unhealthy"
    categories[(aqi >= 201) & (aqi <= 300)] = "Very Unhealthy"
    categories[aqi > 300] = "Hazardous"
    
    if aqi.ndim == 0:  # Scalar input
        return categories.item()
    return categories


def add_aqi_to_dataframe(df):
    """
    Add AQI and category columns to a DataFrame containing pm2_5_atm.
    
    Args:
        df: DataFrame with pm2_5_atm column
        
    Returns:
        DataFrame with additional aqi and aqi_category columns
    """
    df = df.copy()
    df['aqi'] = pm25_to_aqi(df['pm2_5_atm'])
    df['aqi_category'] = aqi_to_category(df['aqi'])
    return df


def get_aqi_category_info():
    """
    Returns information about AQI categories.
    
    Returns:
        Dictionary with category information
    """
    return {
        "Good": {"min": 0, "max": 50, "color": "green", "description": "Air quality is satisfactory"},
        "Moderate": {"min": 51, "max": 100, "color": "yellow", "description": "Air quality is acceptable"},
        "Unhealthy for Sensitive Groups": {"min": 101, "max": 150, "color": "orange", "description": "Members of sensitive groups may experience health effects"},
        "Unhealthy": {"min": 151, "max": 200, "color": "red", "description": "Everyone may begin to experience health effects"},
        "Very Unhealthy": {"min": 201, "max": 300, "color": "purple", "description": "Health alert: everyone may experience more serious health effects"},
        "Hazardous": {"min": 301, "max": 500, "color": "maroon", "description": "Health warning of emergency conditions"}
    }


if __name__ == "__main__":
    # Test AQI calculations
    test_pm25 = [5, 15, 40, 60, 180, 250, 350]
    test_aqi = pm25_to_aqi(test_pm25)
    test_categories = aqi_to_category(test_aqi)
    
    print("PM2.5 to AQI Conversion Test:")
    print("-" * 60)
    for pm, aqi, cat in zip(test_pm25, test_aqi, test_categories):
        print(f"PM2.5: {pm:6.1f} μg/m³  ->  AQI: {aqi:3d}  ({cat})")
    
    # Test with DataFrame
    print("\n\nDataFrame Test:")
    print("-" * 60)
    test_df = pd.DataFrame({
        'pm2_5_atm': [8.5, 22.3, 45.0, 100.0, 200.0]
    })
    result_df = add_aqi_to_dataframe(test_df)
    print(result_df)

