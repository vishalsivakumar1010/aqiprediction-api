# Render Deployment Guide for AQI Prediction API

This guide provides step-by-step instructions for deploying the AQI Prediction API to Render.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Deployment Steps](#deployment-steps)
4. [Configuration](#configuration)
5. [Post-Deployment Verification](#post-deployment-verification)
6. [Troubleshooting](#troubleshooting)
7. [Updating the Deployment](#updating-the-deployment)

---

## Prerequisites

Before deploying, ensure you have:

1. **Render Account**: Sign up at [render.com](https://render.com) (free tier available)
2. **GitHub Repository**: Your code should be in a GitHub repository
   - Repository: `aqiprediction-api` (or your chosen name)
   - All necessary files committed and pushed
3. **PurpleAir API Key**: Your PurpleAir API key for fetching sensor data
4. **Required Files**: All model files and dependencies in the repository

---

## Pre-Deployment Checklist

### 1. Verify Required Files

Ensure your repository contains:

```
aqiprediction-api/
├── aqi_api_server.py          # Main API server
├── test_predictions.py         # Prediction functions
├── aqi_utils.py                # AQI utility functions
├── feature_engineering.py      # Feature engineering functions
├── requirements.txt            # Python dependencies
├── render.yaml                 # Render configuration (optional)
├── models/                     # Trained model files
│   ├── pm25_model_1h.pkl
│   ├── pm25_model_3h.pkl
│   ├── category_model_1h.pkl
│   ├── category_model_3h.pkl
│   ├── category_mapping_1h.pkl
│   ├── category_mapping_3h.pkl
│   ├── feature_columns_1h.pkl
│   └── feature_columns_3h.pkl
└── sensor_locations.pkl        # Sensor location data (or .csv)
```

### 2. Update API Server for Deployment

The API server needs to be updated to work without hardcoded paths. Check that `aqi_api_server.py` uses relative paths or environment variables.

### 3. Test Locally

Before deploying, test the API locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python aqi_api_server.py --host 0.0.0.0 --port 8000

# Test health endpoint
curl http://localhost:8000/health

# Test prediction endpoint
curl "http://localhost:8000/predict/address?address=2523+Bishop+Ave,+Fremont,+CA+94536"
```

---

## Deployment Steps

### Step 1: Prepare Your Repository

1. **Ensure all files are committed**:
   ```bash
   git add .
   git commit -m "Prepare for Render deployment"
   git push origin main
   ```

2. **Verify repository structure** on GitHub

### Step 2: Create a New Web Service on Render

1. **Log in to Render Dashboard**
   - Go to [dashboard.render.com](https://dashboard.render.com)
   - Sign in or create an account

2. **Create New Web Service**
   - Click **"New +"** button
   - Select **"Web Service"**
   - Connect your GitHub account if not already connected
   - Select your repository: `aqiprediction-api`

### Step 3: Configure the Service

Use the following settings:

#### Basic Settings:
- **Name**: `aqi-prediction-api` (or your preferred name)
- **Region**: Choose closest to your users (e.g., `Oregon (US West)`)
- **Branch**: `main` (or your deployment branch)
- **Root Directory**: Leave empty (or specify if code is in a subdirectory)
- **Runtime**: `Python 3`
- **Build Command**: 
  ```bash
  pip install -r requirements.txt
  ```
- **Start Command**: 
  ```bash
  python aqi_api_server.py --host 0.0.0.0 --port $PORT
  ```
  **OR** if using `render.yaml`:
  ```bash
  uvicorn aqi_api_server:app --host 0.0.0.0 --port $PORT
  ```

#### Environment Variables:
Click **"Advanced"** and add these environment variables:

| Key | Value | Description |
|-----|-------|-------------|
| `PURPLEAIR_API_KEY` | `your-api-key-here` | Your PurpleAir API key |
| `PORT` | (auto-set by Render) | Port number (Render sets this automatically) |
| `PYTHON_VERSION` | `3.11` | Python version (optional, recommended) |

**Note**: Render automatically sets `$PORT` - use it in your start command.

### Step 4: Deploy

1. Click **"Create Web Service"**
2. Render will:
   - Clone your repository
   - Install dependencies from `requirements.txt`
   - Start your service
3. Monitor the build logs for any errors

### Step 5: Get Your Service URL

Once deployed, Render provides:
- **Service URL**: `https://aqi-prediction-api.onrender.com` (or your custom domain)
- **Health Check**: `https://aqi-prediction-api.onrender.com/health`
- **API Docs**: `https://aqi-prediction-api.onrender.com/docs`

---

## Configuration

### Using render.yaml (Recommended)

If you created `render.yaml`, Render will automatically use it. This file should be in your repository root:

```yaml
services:
  - type: web
    name: aqi-prediction-api
    env: python
    buildCommand: pip install -r requirements.txt
    # Omit --port so the app reads PORT from the environment (avoids "Option '--port' requires an argument" when $PORT is not expanded)
    startCommand: python aqi_api_server.py --host 0.0.0.0
    envVars:
      - key: PURPLEAIR_API_KEY
        sync: false  # Set this manually in Render dashboard
      - key: PYTHON_VERSION
        value: 3.11
    healthCheckPath: /health
```

### Manual Configuration

If not using `render.yaml`, configure manually in the Render dashboard as described in Step 3.

### Environment Variables

**Required**:
- `PURPLEAIR_API_KEY`: Your PurpleAir API key

**Optional**:
- `PYTHON_VERSION`: Python version (default: 3.11)
- `LOG_LEVEL`: Logging level (default: INFO)

### CORS Configuration

The API is configured to allow CORS from any origin. For production, you may want to restrict this:

In `aqi_api_server.py`, update:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-lovable-app.com"],  # Restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Post-Deployment Verification

### 1. Health Check

```bash
curl https://your-service.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "models_loaded": true,
  "timestamp": "2026-01-XX..."
}
```

### 2. Test Prediction Endpoint

```bash
# Test with address
curl "https://your-service.onrender.com/predict/address?address=2523+Bishop+Ave,+Fremont,+CA+94536"

# Test with coordinates
curl "https://your-service.onrender.com/predict?latitude=37.5483&longitude=-121.9886"
```

### 3. Check API Documentation

Visit: `https://your-service.onrender.com/docs`

You should see the Swagger UI with all available endpoints.

### 4. Test from Your Application

Update your Lovable app or frontend to use the new Render URL:
```javascript
const API_URL = "https://your-service.onrender.com";
```

---

## Troubleshooting

### Issue: Build Fails

**Symptoms**: Build logs show errors during `pip install`

**Solutions**:
1. Check `requirements.txt` for correct package versions
2. Ensure Python version is compatible (3.9+)
3. Check build logs for specific error messages
4. Try updating package versions if conflicts occur

### Issue: Service Crashes on Start

**Symptoms**: Service starts but immediately crashes

**Solutions**:
1. Check logs in Render dashboard
2. Verify all model files are present in `models/` directory
3. Ensure `sensor_locations.pkl` exists
4. Check that `PURPLEAIR_API_KEY` is set correctly
5. Verify file paths are relative, not absolute

### Issue: Models Not Loading

**Symptoms**: Health check shows `models_loaded: false`

**Solutions**:
1. Verify `models/` directory is committed to Git
2. Check file paths in `test_predictions.py` - should be relative
3. Ensure model files are not in `.gitignore`
4. Check logs for specific file not found errors

### Issue: "Error: Option '--port' requires an argument"

**Symptoms**: Deploy fails immediately with uvicorn error about `--port` requiring an argument.

**Cause**: The start command uses `uvicorn ... --port $PORT` and `$PORT` is not expanded (empty), so uvicorn receives no port value.

**Solutions**:
1. **Recommended**: Use the app entrypoint so the app reads `PORT` from the environment. In Render dashboard **Start Command**, set:
   ```bash
   python aqi_api_server.py --host 0.0.0.0 --data-dir . --model-dir P2-RouteFinder/models/v2_cleaned
   ```
   Do **not** pass `--port $PORT`; the app uses `os.environ.get('PORT', 8000)` when `--port` is omitted.
2. If you prefer uvicorn directly, use a shell so `$PORT` is expanded, e.g. `sh -c 'uvicorn aqi_api_server:app --host 0.0.0.0 --port $PORT'`.

### Issue: 502 Bad Gateway

**Symptoms**: Service returns 502 errors

**Solutions**:
1. Check if service is running (may have crashed)
2. Use start command `python aqi_api_server.py --host 0.0.0.0` (app reads `PORT` from environment)
3. Check health endpoint to see if service is responding
4. Review logs for runtime errors

### Issue: Slow Response Times

**Symptoms**: API responses are slow (>5 seconds)

**Solutions**:
1. Render free tier may spin down after inactivity
2. First request after spin-down can take 30-60 seconds
3. Consider upgrading to paid tier for always-on service
4. Implement health check pings to keep service warm

### Issue: CORS Errors

**Symptoms**: Frontend can't access API due to CORS

**Solutions**:
1. Verify CORS middleware is configured in `aqi_api_server.py`
2. Check `allow_origins` includes your frontend domain
3. For development, `allow_origins=["*"]` is acceptable
4. For production, specify exact domains

### Issue: PurpleAir API Errors

**Symptoms**: Predictions fail with API key errors

**Solutions**:
1. Verify `PURPLEAIR_API_KEY` is set in Render environment variables
2. Check API key is valid and not expired
3. Test API key locally first
4. Check PurpleAir API status

---

## Updating the Deployment

### Method 1: Automatic (via Git)

1. Make changes to your code
2. Commit and push to GitHub:
   ```bash
   git add .
   git commit -m "Update API"
   git push origin main
   ```
3. Render automatically detects changes and redeploys
4. Monitor deployment in Render dashboard

### Method 2: Manual Redeploy

1. Go to Render dashboard
2. Select your service
3. Click **"Manual Deploy"**
4. Select branch/commit to deploy

### Updating Models

If you retrain models:

1. Replace model files in `models/` directory
2. Commit and push:
   ```bash
   git add models/
   git commit -m "Update trained models"
   git push origin main
   ```
3. Render will redeploy automatically
4. Models will be loaded on next service start

---

## Render Free Tier Limitations

**Important Notes**:

1. **Spin-down**: Free tier services spin down after 15 minutes of inactivity
   - First request after spin-down takes 30-60 seconds
   - Subsequent requests are fast

2. **Resource Limits**:
   - 512 MB RAM
   - 0.1 CPU
   - 100 GB bandwidth/month

3. **Recommendations**:
   - Use paid tier for production (always-on, better performance)
   - Implement health check pings to keep service warm
   - Monitor usage to avoid bandwidth limits

---

## Security Best Practices

1. **API Keys**: Never commit API keys to Git
   - Use Render environment variables
   - Add `.env` to `.gitignore` if using locally

2. **CORS**: Restrict CORS to specific domains in production

3. **Rate Limiting**: Consider adding rate limiting for production:
   ```python
   from slowapi import Limiter
   limiter = Limiter(key_func=get_remote_address)
   ```

4. **HTTPS**: Render provides HTTPS automatically

5. **Error Messages**: Don't expose sensitive information in error messages

---

## Monitoring and Logs

### View Logs

1. Go to Render dashboard
2. Select your service
3. Click **"Logs"** tab
4. View real-time and historical logs

### Set Up Alerts

1. In Render dashboard, go to service settings
2. Configure email alerts for:
   - Service crashes
   - Build failures
   - High error rates

---

## Cost Estimation

**Free Tier**:
- $0/month
- 15-minute spin-down
- 512 MB RAM
- 0.1 CPU

**Starter Tier** ($7/month):
- Always-on service
- 512 MB RAM
- 0.5 CPU
- Better performance

**Standard Tier** ($25/month):
- Always-on service
- 2 GB RAM
- 1 CPU
- Production-ready

---

## Support

- **Render Documentation**: [render.com/docs](https://render.com/docs)
- **Render Support**: [community.render.com](https://community.render.com)
- **API Issues**: Check logs in Render dashboard
- **Model Issues**: Review `test_predictions.py` and model loading logic

---

## Quick Reference

**Service URL**: `https://your-service.onrender.com`

**Endpoints**:
- Health: `GET /health`
- Predict (address): `GET /predict/address?address=...`
- Predict (coords): `GET /predict?latitude=...&longitude=...`
- Docs: `GET /docs`

**Environment Variables**:
- `PURPLEAIR_API_KEY` (required)
- `PORT` (auto-set by Render)
- `PYTHON_VERSION` (optional)

**Start Command**:
```bash
python aqi_api_server.py --host 0.0.0.0 --port $PORT
```

---

**Last Updated**: January 2026
