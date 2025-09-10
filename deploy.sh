#!/bin/bash

# Deployment script for Net-premium-checker
# This script will be called by GitHub Actions

set -e  # Exit on any error

echo "🚀 Starting deployment..."

# Navigate to project directory
cd /root/Net-premium-checker

# Pull latest changes
echo "📥 Pulling latest changes..."
git pull origin main

# Install/update Python dependencies
echo "🐍 Installing Python dependencies..."
pip3 install -r requirements.txt

# Install/update Node.js dependencies and build frontend
echo "📦 Installing Node.js dependencies..."
cd frontend
npm install
npm run build
cd ..

# Stop existing backend process
echo "🛑 Stopping existing backend..."
pkill -f "python main.py" || true
sleep 2

# Start backend service
echo "▶️ Starting backend service..."
nohup python main.py > backend.log 2>&1 &
sleep 3

# Check if backend is running
if pgrep -f "python main.py" > /dev/null; then
    echo "✅ Backend started successfully"
else
    echo "❌ Backend failed to start"
    exit 1
fi

# Reload Nginx
echo "🔄 Reloading Nginx..."
systemctl reload nginx

echo "🎉 Deployment completed successfully!"
echo "🌐 Application is available at: https://premiumcalculator.levitascapital.in"
