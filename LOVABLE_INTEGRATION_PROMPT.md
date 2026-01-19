# Lovable UI Integration - AQI Prediction API

## Copy this entire prompt to Lovable:

---

I need to integrate an AQI (Air Quality Index) prediction API into my Lovable application. Here are the complete API specifications:

## API Server

**Base URL**: `http://localhost:8000`

The API server is already running and provides Air Quality Index predictions for locations in Fremont, CA. It uses machine learning models to predict both 1-hour and 3-hour AQI forecasts.

## API Endpoints

### 1. Health Check
```
GET /health
```
Returns API status. No parameters needed.

**Response**:
```json
{
  "status": "healthy",
  "models_loaded": true,
  "timestamp": "2026-01-10T12:00:00"
}
```

### 2. Predict by Address (GET - Recommended)
```
GET /predict/address?address={url_encoded_address}
```

**Parameters**:
- `address` (required): Full address in Fremont, CA, URL-encoded
  - Example: `2523+Bishop+Ave,+Fremont,+CA+94536`

**Example Request**:
```javascript
fetch('http://localhost:8000/predict/address?address=2523+Bishop+Ave,+Fremont,+CA+94536')
  .then(res => res.json())
  .then(data => console.log(data));
```

### 3. Predict by Address or Coordinates (POST)
```
POST /predict
Content-Type: application/json
```

**Request Body**:
```json
{
  "address": "2523 Bishop Ave, Fremont, CA 94536"
}
```

OR

```json
{
  "latitude": 37.563332,
  "longitude": -121.993722
}
```

**Example Request**:
```javascript
fetch('http://localhost:8000/predict', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    address: "2523 Bishop Ave, Fremont, CA 94536"
  })
})
  .then(res => res.json())
  .then(data => console.log(data));
```

## Response Format

**Success Response** (200 OK):
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

**Error Response** (400/500):
```json
{
  "detail": "Error message describing what went wrong"
}
```

## AQI Category Color Scheme (EPA Standards)

Use these exact colors for category badges/indicators:

- **Good** (0-50): `#00E400` (Green)
- **Moderate** (51-100): `#FFFF00` (Yellow)
- **Unhealthy for Sensitive Groups** (101-150): `#FF7E00` (Orange)
- **Unhealthy** (151-200): `#FF0000` (Red)
- **Very Unhealthy** (201-300): `#8F3F97` (Purple)
- **Hazardous** (301+): `#7E0023` (Maroon)

## UI Requirements

Please create a beautiful, modern, mobile-responsive web application with the following features:

### 1. Main Search Interface
- **Address Input**: Text input field with placeholder "Enter address in Fremont, CA"
- **Search Button**: Prominent "Get AQI Forecast" button
- **Loading State**: Show spinner/loading indicator while API call is in progress (typically 2-5 seconds)
- **Error Display**: Show user-friendly error messages if API call fails

### 2. Current AQI Display Card
Display current air quality prominently:
- **Large AQI Number**: Display `current_aqi.aqi` in large, bold font (size: 48-72px)
- **Category Badge**: Color-coded badge showing `current_aqi.category` using the color scheme above
- **PM2.5 Value**: Show `current_aqi.pm25_ugm3` with unit "μg/m³"
- **Weather Info**: Temperature (`current_aqi.temperature_f` °F) and Humidity (`current_aqi.humidity_percent`%)
- **Timestamp**: Show when data was collected (`timestamp` field)

### 3. Forecast Cards
Create two side-by-side (or stacked on mobile) forecast cards:

**1-Hour Forecast Card**:
- Title: "1-Hour Forecast"
- AQI: `forecast_1h.aqi` with category badge
- PM2.5: `forecast_1h.pm25_ugm3` μg/m³
- Trend Indicator: Arrow up/down/sideways comparing to current AQI

**3-Hour Forecast Card**:
- Title: "3-Hour Forecast"
- AQI: `forecast_3h.aqi` with category badge
- PM2.5: `forecast_3h.pm25_ugm3` μg/m³
- Trend Indicator: Arrow up/down/sideways comparing to current AQI

### 4. Sensor Information
Small info section showing:
- "Data from: {sensor_info.sensor_name}" 
- "Distance: {sensor_info.distance_km} km from your location"

### 5. Design Specifications
- **Layout**: Clean, card-based design with proper spacing
- **Typography**: Clear hierarchy, readable fonts (sans-serif recommended)
- **Colors**: Use the AQI color scheme for category badges, neutral grays for UI elements
- **Animations**: Smooth transitions when data loads, subtle hover effects on buttons
- **Mobile**: Fully responsive, stack cards vertically on small screens
- **Accessibility**: Proper ARIA labels, keyboard navigation support

### 6. Additional Features (Nice to Have)
- **Auto-refresh**: Option to refresh data every 5-10 minutes
- **Favorites**: Save frequently used addresses
- **Comparison View**: Visual chart/graph showing current vs forecasts
- **History**: Store and display previous predictions (localStorage)
- **Share**: Generate shareable link with address and results

### 7. Error Handling
Handle these error scenarios gracefully:
- **Network Error**: "Unable to connect to API. Please check your connection."
- **Invalid Address**: "Could not find that address. Please enter a valid Fremont, CA address."
- **API Error**: "Prediction service temporarily unavailable. Please try again later."
- **Empty Address**: Show validation message before API call

## TypeScript Interface

Use this TypeScript interface for type safety:

```typescript
interface AQIPredictionResponse {
  success: boolean;
  timestamp: string;
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

## Example Implementation

Here's a simple React component structure to get started:

```typescript
// AQIWidget.tsx
import { useState } from 'react';

function AQIWidget() {
  const [address, setAddress] = useState('');
  const [data, setData] = useState<AQIPredictionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAQI = async () => {
    if (!address.trim()) {
      setError('Please enter an address');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const encodedAddress = encodeURIComponent(address);
      const response = await fetch(
        `http://localhost:8000/predict/address?address=${encodedAddress}`
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'API request failed');
      }

      const result = await response.json();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
    } finally {
      setLoading(false);
    }
  };

  // Render UI components here...
}
```

## Test Addresses

Use these addresses for testing:
1. "2523 Bishop Ave, Fremont, CA 94536"
2. "39400 Paseo Padre Pkwy, Fremont, CA 94538"
3. "4620 Mattos Dr, Fremont, CA 94536"
4. "5400 Mowry Ave, Fremont, CA 94538"
5. "40500 Paseo Padre Pkwy, Fremont, CA 94538"

## Technical Notes

- **CORS**: API has CORS enabled, so cross-origin requests from your Lovable app will work
- **Response Time**: Typical API response time is 2-5 seconds (includes geocoding, sensor lookup, and prediction)
- **No Auth**: Currently no authentication required
- **Rate Limits**: No built-in rate limiting (implement client-side throttling if needed)

Please build this UI using React/TypeScript with modern best practices, proper error handling, beautiful styling, and full mobile responsiveness. Make it production-ready and user-friendly!

---
