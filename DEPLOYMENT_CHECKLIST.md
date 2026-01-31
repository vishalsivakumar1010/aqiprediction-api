# Render Deployment Checklist

Use this checklist to ensure a smooth deployment to Render.

## Pre-Deployment

- [ ] **Run preparation script**:
  ```bash
  ./prepare_for_render.sh
  ```

- [ ] **Verify all required files exist**:
  - [ ] `aqi_api_server.py`
  - [ ] `test_predictions.py`
  - [ ] `aqi_utils.py` (or copied from original pipeline)
  - [ ] `feature_engineering.py` (or copied from original pipeline)
  - [ ] `requirements.txt`
  - [ ] `render.yaml` (optional but recommended)
  - [ ] `models/` directory with all 8 model files
  - [ ] `sensor_locations.pkl` or `sensor_locations.csv`

- [ ] **Test locally**:
  ```bash
  pip install -r requirements.txt
  python aqi_api_server.py --host 0.0.0.0 --port 8000
  curl http://localhost:8000/health
  ```

- [ ] **Verify Git repository**:
  - [ ] All files committed
  - [ ] Pushed to GitHub
  - [ ] Repository is accessible

- [ ] **Get PurpleAir API Key**:
  - [ ] API key is ready
  - [ ] Key is valid and active

## Deployment Steps

- [ ] **Create Render account** (if needed)
  - [ ] Sign up at render.com
  - [ ] Connect GitHub account

- [ ] **Create new Web Service**:
  - [ ] Click "New +" → "Web Service"
  - [ ] Select repository: `aqiprediction-api`
  - [ ] Set name: `aqi-prediction-api`

- [ ] **Configure service**:
  - [ ] Region: Choose closest to users
  - [ ] Branch: `main`
  - [ ] Runtime: `Python 3`
  - [ ] Build Command: `pip install -r requirements.txt`
  - [ ] Start Command: `python aqi_api_server.py --host 0.0.0.0 --port $PORT`

- [ ] **Set environment variables**:
  - [ ] `PURPLEAIR_API_KEY` = (your API key)
  - [ ] `PYTHON_VERSION` = `3.11` (optional)

- [ ] **Deploy**:
  - [ ] Click "Create Web Service"
  - [ ] Monitor build logs
  - [ ] Wait for deployment to complete

## Post-Deployment Verification

- [ ] **Health check**:
  ```bash
  curl https://your-service.onrender.com/health
  ```
  Expected: `{"status": "healthy", "models_loaded": true, ...}`

- [ ] **Test prediction endpoint**:
  ```bash
  curl "https://your-service.onrender.com/predict/address?address=2523+Bishop+Ave,+Fremont,+CA+94536"
  ```
  Expected: JSON response with predictions

- [ ] **Check API documentation**:
  - [ ] Visit: `https://your-service.onrender.com/docs`
  - [ ] Verify all endpoints are listed
  - [ ] Test endpoints from Swagger UI

- [ ] **Update frontend/application**:
  - [ ] Update API URL in Lovable app
  - [ ] Test integration
  - [ ] Verify predictions work

## Troubleshooting

If deployment fails:

- [ ] Check build logs in Render dashboard
- [ ] Verify all files are in repository
- [ ] Check `requirements.txt` for correct versions
- [ ] Verify `PURPLEAIR_API_KEY` is set
- [ ] Check that model files are not in `.gitignore`
- [ ] Review error messages in logs

## Common Issues

- [ ] **Build fails**: Check Python version compatibility
- [ ] **Models not loading**: Verify `models/` directory is committed
- [ ] **502 errors**: Check start command uses `$PORT`
- [ ] **Slow first request**: Normal on free tier (spin-down)
- [ ] **CORS errors**: Verify CORS middleware is configured

## Notes

- Free tier services spin down after 15 minutes of inactivity
- First request after spin-down takes 30-60 seconds
- Consider paid tier for production (always-on service)
- Monitor usage to avoid bandwidth limits

---

**Service URL**: `https://your-service.onrender.com`

**Documentation**: See `RENDER_DEPLOYMENT.md` for detailed instructions.
