# Render Deployment - Quick Start

## 🚀 Quick Deployment Steps

### 1. Prepare Your Repository

```bash
# Run the preparation script
./prepare_for_render.sh

# Verify all files are present
ls -la aqi_api_server.py test_predictions.py aqi_utils.py feature_engineering.py
ls -la models/*.pkl
ls -la sensor_locations.*
```

### 2. Commit and Push to GitHub

```bash
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

### 3. Deploy on Render

1. **Go to [dashboard.render.com](https://dashboard.render.com)**
2. **Click "New +" → "Web Service"**
3. **Connect your GitHub repository**: `aqiprediction-api`
4. **Configure**:
   - **Name**: `aqi-prediction-api`
   - **Region**: Choose closest to users
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python aqi_api_server.py --host 0.0.0.0 --port $PORT`
5. **Add Environment Variable**:
   - **Key**: `PURPLEAIR_API_KEY`
   - **Value**: Your PurpleAir API key
6. **Click "Create Web Service"**

### 4. Verify Deployment

```bash
# Health check
curl https://your-service.onrender.com/health

# Test prediction
curl "https://your-service.onrender.com/predict/address?address=2523+Bishop+Ave,+Fremont,+CA+94536"
```

## 📋 Required Files

Your repository must contain:

```
aqiprediction-api/
├── aqi_api_server.py          # Main API server
├── test_predictions.py         # Prediction functions
├── aqi_utils.py                # AQI utilities
├── feature_engineering.py      # Feature engineering
├── requirements.txt            # Python dependencies
├── render.yaml                 # Render config (optional)
├── models/                     # Trained models
│   ├── pm25_model_1h.pkl
│   ├── pm25_model_3h.pkl
│   ├── category_model_1h.pkl
│   ├── category_model_3h.pkl
│   ├── category_mapping_1h.pkl
│   ├── category_mapping_3h.pkl
│   ├── feature_columns_1h.pkl
│   └── feature_columns_3h.pkl
└── sensor_locations.pkl        # Sensor locations
```

## 🔑 Environment Variables

**Required**:
- `PURPLEAIR_API_KEY`: Your PurpleAir API key

**Optional**:
- `PYTHON_VERSION`: `3.11` (default)

## 📚 Documentation

- **Full Guide**: See `RENDER_DEPLOYMENT.md` for detailed instructions
- **Checklist**: See `DEPLOYMENT_CHECKLIST.md` for step-by-step checklist
- **Troubleshooting**: See `RENDER_DEPLOYMENT.md` → Troubleshooting section

## ⚠️ Important Notes

1. **Free Tier**: Services spin down after 15 minutes of inactivity
   - First request after spin-down takes 30-60 seconds
   - Consider paid tier for production

2. **Model Files**: Ensure all model files are committed to Git (not in `.gitignore`)

3. **API Key**: Never commit API keys to Git - use Render environment variables

4. **CORS**: API is configured to allow all origins. Restrict in production if needed.

## 🆘 Need Help?

- Check build logs in Render dashboard
- Review `RENDER_DEPLOYMENT.md` for detailed troubleshooting
- Verify all files are in repository
- Test locally before deploying

---

**Service URL**: `https://your-service.onrender.com`  
**API Docs**: `https://your-service.onrender.com/docs`  
**Health Check**: `https://your-service.onrender.com/health`
