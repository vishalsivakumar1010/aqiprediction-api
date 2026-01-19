# Lovable Integration Prompt

Copy and paste this entire prompt into Lovable to integrate the AQI Prediction API:

---

## AQI Prediction API Integration

I have a REST API for predicting Air Quality Index (AQI) forecasts that I want to integrate into my Lovable UI application. Here are the API details:

### API Base URL
```
http://localhost:8000
```
*(Note: Update this URL to your deployed server URL when ready)*

### API Endpoints

#### 1. Health Check
**GET** `/health`
- Checks if API is running
- Returns: `{ "status": "healthy", "models_loaded": true, "timestamp": "..." }`

#### 2. Predict by Address (Recommended)
**GET** `/predict/address?address={url_encoded_address}`

**Example**:
```
GET /predict/address?address=2523+Bishop+Ave,+Fremont,+CA+94536
```

**Response Format**:
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

#### 3. Predict by Coordinates (Alternative)
**POST** `/predict`
**Body** (JSON):
```json
{
  "latitude": 37.563332,
  "longitude": -121.993722
}
```
*(Same response format as GET endpoint)*

### What I Need from Lovable

Please create a beautiful, modern UI component that:

1. **Address Input Form**:
   - Text input field for entering an address in Fremont, CA
   - Submit button to trigger prediction
   - Loading state while fetching data
   - Error handling with user-friendly messages

2. **Display Current AQI**:
   - Large, prominent display of current AQI number
   - Color-coded category badge (Good=green, Moderate=yellow, Unhealthy=orange, etc.)
   - Current PM2.5 value in μg/m³
   - Temperature and humidity (if available)
   - Timestamp of when data was collected

3. **Display Forecasts**:
   - **1-Hour Forecast**: AQI number, category, PM2.5 value
   - **3-Hour Forecast**: AQI number, category, PM2.5 value
   - Visual comparison (e.g., arrows showing if AQI is improving/worsening)
   - Color coding for each forecast category

4. **Additional Information**:
   - Sensor name and distance from user's location
   - Address that was used for prediction
   - Visual indicator of data freshness

5. **Design Requirements**:
   - Clean, modern, mobile-responsive design
   - Use appropriate color scheme:
     - Green (Good): #00E400
     - Yellow (Moderate): #FFFF00
     - Orange (Unhealthy for Sensitive Groups): #FF7E00
     - Red (Unhealthy): #FF0000
     - Purple (Very Unhealthy): #8F3F97
     - Maroon (Hazardous): #7E0023
   - Smooth transitions and animations
   - Card-based layout
   - Clear typography hierarchy

6. **Features**:
   - Auto-refresh option (e.g., refresh every 5 minutes)
   - Save favorite addresses/locations
   - Share functionality
   - Historical trend visualization (if storing multiple predictions)

### Example Addresses to Test With
- "2523 Bishop Ave, Fremont, CA 94536"
- "39400 Paseo Padre Pkwy, Fremont, CA 94538"
- "4620 Mattos Dr, Fremont, CA 94536"

### Error Handling
The API may return:
- **400**: Bad request (invalid address)
- **500**: Server error (sensor data unavailable, prediction failed)
- **503**: Service unavailable (models not loaded)

Display user-friendly error messages for each case.

### Technical Notes
- API uses CORS (cross-origin requests enabled)
- Response time: typically 2-5 seconds
- No authentication required (for now)
- All addresses should be in Fremont, CA area

Please build this UI with React/TypeScript using best practices, proper error handling, and beautiful styling. Use the response schema provided above for TypeScript types.

---
