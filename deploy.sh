#!/bin/bash

# Navigate to the actual project directory
cd /opt/net-premium-checker

# Pull the latest changes from GitHub
echo "Pulling latest changes..."
git pull origin master

# Activate virtual environment and install Python dependencies
echo "Installing Python dependencies..."
source venv/bin/activate
pip install -r requirements.txt
deactivate

# Build the frontend with increased memory
echo "Building frontend..."
cd frontend
npm install
# Increase Node.js memory limit for build
NODE_OPTIONS="--max-old-space-size=4096" npm run build
cd ..

# Restart the PM2 process
echo "Restarting PM2 process..."
pm2 restart net-premium-checker-backend

# Reload Nginx
echo "Reloading Nginx..."
systemctl reload nginx

echo "Deployment completed successfully!"