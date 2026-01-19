# AQI Prediction API - Quick Start Guide

## Starting the API Server

### 1. Install Dependencies
```bash
cd "/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC"
pip3 install -r api_requirements.txt
```

### 2. Start the Server
```bash
python3 aqi_api_server.py --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API**: `http://localhost:8000`
- **Interactive Docs**: `http://localhost:8000/docs` (Swagger UI)
- **Alternative Docs**: `http://localhost:8000/redoc`

### 3. Test the API
```bash
# Health check
curl http://localhost:8000/health

# Test prediction
curl "http://localhost:8000/predict/address?address=2523+Bishop+Ave,+Fremont,+CA+94536"
```

## For Production Deployment

Use uvicorn with multiple workers:
```bash
uvicorn aqi_api_server:app --host 0.0.0.0 --port 8000 --workers 4
```

Or use gunicorn with uvicorn workers:
```bash
gunicorn aqi_api_server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```
