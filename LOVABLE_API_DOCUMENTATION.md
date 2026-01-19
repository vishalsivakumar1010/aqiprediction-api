# AQI Prediction API - Integration Guide for Lovable

## API Overview

This API provides real-time Air Quality Index (AQI) predictions for locations in Fremont, CA. It predicts both 1-hour and 3-hour forecasts using machine learning models trained on PurpleAir sensor data.

**Base URL**: `http://localhost:8000` (or your deployed server URL)

## Quick Start

### Starting the API Server

```bash
cd "/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC"
python3 aqi_api_server.py --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API Endpoints**: `http://localhost:8000`
- **Interactive Docs**: `http://localhost:8000/docs` (Swagger UI)
- **Health Check**: `http://localhost:8000/health`

## API Endpoints

### 1. Health Check
**GET** `/health`

Check if the API is running and models are loaded.

**Response**:
```json
{
  "status": "healthy",
  "models_loaded": true,
  "timestamp": "2026-01-10T12:00:00"
}
```

### 2. Predict by Address (GET)
**GET** `/predict/address?address={address}&api-key={optional_key}`

Predict AQI for an address in Fremont, CA.

**Query Parameters**:
- `address` (required): Full address, e.g., `"2523 Bishop Ave, Fremont, CA 94536"`
- `api-key` (optional): PurpleAir API key (if not set at server startup)

**Example Request**:
```
GET /predict/address?address=2523+Bishop+Ave,+Fremont,+CA+94536
```

**Example Response**:
```json
{
  "success": true,
  "timestamp": "2026-01-10T12:00:00",
  "location": {
    "address": "2523 Bishop Ave, Fremont, CA 94536",
    "latitude": 37.563332,
    "longitude": -121.993722
  },
  "current_aqi": {
    "pm25_ugm3": 22.6,
    "aqi": 73,
    "category": "Moderate",
    "temperature_f": 71.0,
    "humidity_percent": 28.0
  },
  "forecast_1h": {
    "pm25_ugm3": 32.25,
    "aqi": 93,
    "category": "Moderate"
  },
  "forecast_3h": {
    "pm25_ugm3": 43.12,
    "aqi": 120,
    "category": "Unhealthy for Sensitive Groups"
  },
  "sensor_info": {
    "sensor_id": 71443,
    "sensor_name": "MoonRiver",
    "distance_km": 0.30,
    "latitude": 37.561237,
    "longitude": -121.991510
  }
}
```

### 3. Predict by Address or Coordinates (POST)
**POST** `/predict`

More flexible endpoint that accepts address or coordinates in JSON body.

**Request Body** (JSON):
```json
{
  "address": "2523 Bishop Ave, Fremont, CA 94536",
  "latitude": 37.563332,    // Optional if address provided
  "longitude": -121.993722,  // Optional if address provided
  "api_key": "YOUR_KEY"      // Optional (uses server default)
}
```

**Response**: Same as GET `/predict/address`

**Example using coordinates only**:
```json
{
  "latitude": 37.563332,
  "longitude": -121.993722
}
```

## AQI Categories

The API returns AQI categories based on EPA standards:
- **Good** (0-50): Air quality is satisfactory
- **Moderate** (51-100): Acceptable for most people
- **Unhealthy for Sensitive Groups** (101-150): Sensitive groups may experience health effects
- **Unhealthy** (151-200): Everyone may begin to experience health effects
- **Very Unhealthy** (201-300): Health alert - everyone may experience serious health effects
- **Hazardous** (301+): Health warning - emergency conditions

## Error Responses

All errors return HTTP status codes with JSON error details:

**400 Bad Request**:
```json
{
  "detail": "Either 'address' or 'latitude' and 'longitude' must be provided"
}
```

**500 Internal Server Error**:
```json
{
  "detail": "Prediction error: Could not fetch current sensor data"
}
```

**503 Service Unavailable**:
```json
{
  "detail": "Models not loaded. API not initialized."
}
```

## Integration Examples

### JavaScript/Fetch (for Lovable)
```javascript
// GET request example
async function getAQIPrediction(address) {
  const response = await fetch(
    `http://localhost:8000/predict/address?address=${encodeURIComponent(address)}`
  );
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  
  const data = await response.json();
  return data;
}

// POST request example
async function predictAQI(address) {
  const response = await fetch('http://localhost:8000/predict', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      address: address
    })
  });
  
  const data = await response.json();
  return data;
}

// Usage
const result = await getAQIPrediction("2523 Bishop Ave, Fremont, CA 94536");
console.log(`Current AQI: ${result.current_aqi.aqi} (${result.current_aqi.category})`);
console.log(`1h Forecast: ${result.forecast_1h.aqi} (${result.forecast_1h.category})`);
console.log(`3h Forecast: ${result.forecast_3h.aqi} (${result.forecast_3h.category})`);
```

### React Component Example
```jsx
import { useState, useEffect } from 'react';

function AQIPrediction({ address }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchAQI() {
      try {
        setLoading(true);
        const response = await fetch(
          `http://localhost:8000/predict/address?address=${encodeURIComponent(address)}`
        );
        
        if (!response.ok) {
          throw new Error('Failed to fetch AQI prediction');
        }
        
        const result = await response.json();
        setData(result);
        setError(null);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    if (address) {
      fetchAQI();
    }
  }, [address]);

  if (loading) return <div>Loading AQI prediction...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!data) return null;

  return (
    <div>
      <h2>Current AQI: {data.current_aqi.aqi} ({data.current_aqi.category})</h2>
      <p>PM2.5: {data.current_aqi.pm25_ugm3} μg/m³</p>
      
      <h3>1-Hour Forecast</h3>
      <p>AQI: {data.forecast_1h.aqi} ({data.forecast_1h.category})</p>
      <p>PM2.5: {data.forecast_1h.pm25_ugm3} μg/m³</p>
      
      <h3>3-Hour Forecast</h3>
      <p>AQI: {data.forecast_3h.aqi} ({data.forecast_3h.category})</p>
      <p>PM2.5: {data.forecast_3h.pm25_ugm3} μg/m³</p>
    </div>
  );
}
```

## Response Schema

### PredictionResponse
```typescript
interface PredictionResponse {
  success: boolean;
  timestamp: string;  // ISO 8601 format
  location: {
    address: string;
    latitude: number;
    longitude: number;
  };
  current_aqi: {
    pm25_ugm3: number;
    aqi: number;
    category: string;
    temperature_f: number;
    humidity_percent: number;
  };
  forecast_1h: {
    pm25_ugm3: number;
    aqi: number;
    category: string;
  };
  forecast_3h: {
    pm25_ugm3: number;
    aqi: number;
    category: string;
  };
  sensor_info: {
    sensor_id: number;
    sensor_name: string;
    distance_km: number;
    latitude: number;
    longitude: number;
  };
}
```

## Notes for Lovable Integration

1. **CORS**: The API has CORS enabled for all origins (you may want to restrict this in production)

2. **Address Format**: Addresses should include city and state (Fremont, CA) for best geocoding results

3. **Response Time**: Typical response time is 2-5 seconds (includes geocoding, sensor lookup, wind data fetch, and prediction)

4. **Rate Limits**: No built-in rate limiting - implement in your application if needed

5. **Error Handling**: Always check the `success` field in the response and handle HTTP error status codes

6. **Caching**: Consider caching results for the same address/coordinates within a short time window (e.g., 5-10 minutes) to reduce API calls

7. **Deployment**: For production, deploy using a production ASGI server like:
   ```bash
   uvicorn aqi_api_server:app --host 0.0.0.0 --port 8000 --workers 4
   ```
