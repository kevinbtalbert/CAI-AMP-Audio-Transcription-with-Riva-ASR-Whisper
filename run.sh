#!/bin/bash
# Quick start script for Healthcare Call Analytics

echo "🏥 Healthcare Call Analytics - Starting..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies if needed
if [ ! -f "venv/installed" ]; then
    echo "📥 Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    touch venv/installed
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating from template..."
    if [ -f ".env.template" ]; then
        cp .env.template .env
        echo "✏️  Please edit .env and add your NVIDIA_NIM_API_KEY"
    fi
fi

# Create necessary directories
mkdir -p audio_files results static

# Run the application
echo ""
echo "🚀 Starting server..."
echo "📱 Open http://localhost:8000 in your browser"
echo ""
python app.py

