#!/bin/bash

# AWS Billing Data Collector - Quick Setup Script

set -e

echo "🚀 AWS Billing Data Collector Setup"
echo "=================================="

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is required but not installed."
    exit 1
fi

echo "✅ pip3 found"

# Install requirements
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data logs

# Copy environment template if .env doesn't exist
if [ ! -f .env ]; then
    echo "📋 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your AWS credentials and Prometheus URL"
fi

# Run setup test
echo "🧪 Running setup validation..."
python3 scripts/test_setup.py

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your AWS credentials and Prometheus URL"
echo "2. Test the collector: python3 scripts/collect_billing_data.py"
echo "3. Push to Prometheus: python3 scripts/push_to_prometheus.py"
echo "4. Set up GitHub Secrets for automated collection"
echo ""
echo "For more information, see README.md"