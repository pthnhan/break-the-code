#!/bin/bash

# Server deployment script
echo "🚀 Deploying Break the Code webapp..."

# Pull latest changes
git pull origin main

# Install/update dependencies
pip install -r requirements.txt

# Stop existing process
pkill -f "gunicorn.*app:app" || true

# Start the application
nohup gunicorn --worker-class gevent -w 1 --bind 0.0.0.0:5000 app:app > app.log 2>&1 &

echo "✅ Deployment complete! App running on port 5000" 