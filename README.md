# ベテランAI Test Deploy

## 🚀 Manual Render Setup Instructions

### 1. Render Dashboard
1. Go to https://dashboard.render.com/
2. Click "New +" → "Web Service"
3. Connect GitHub repository: `IKEMENLTD/dify-rag002`
4. Choose branch: `main`

### 2. Service Settings
- **Name**: `veteranai-final-test`
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app`
- **Plan**: `Free`

### 3. Environment Variables
- `PYTHON_VERSION`: `3.11.7`

### 4. Expected URLs
- Main: https://veteranai-final-test.onrender.com/
- Ping: https://veteranai-final-test.onrender.com/ping
- Dashboard: https://veteranai-final-test.onrender.com/dashboard

## 📋 Files
- `app.py` - Main Flask application
- `requirements.txt` - Flask + gunicorn
- `runtime.txt` - Python version
- `Procfile` - Deployment configuration

## 🔧 Local Testing
```bash
python3 test-local.py
```

## 🌐 Live URLs
After manual setup, the service should be available at:
- https://veteranai-final-test.onrender.com/