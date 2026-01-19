#!/usr/bin/env bash
# Render build script - installs system dependencies and Python packages

set -o errexit  # Exit on error

echo "📦 Installing Chromium..."
apt-get update
apt-get install -y chromium chromium-driver

echo "🐍 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Build complete!"
