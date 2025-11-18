@echo off
REM AWS Billing Data Collector - Quick Setup Script for Windows

echo 🚀 AWS Billing Data Collector Setup
echo ==================================

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is required but not installed.
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

echo ✅ Python found
python --version

REM Check if pip is installed
pip --version >nul 2>&1
if errorlevel 1 (
    echo ❌ pip is required but not installed.
    pause
    exit /b 1
)

echo ✅ pip found

REM Install requirements
echo 📦 Installing Python dependencies...
pip install -r requirements.txt

REM Create necessary directories
echo 📁 Creating directories...
if not exist "data" mkdir data
if not exist "logs" mkdir logs

REM Copy environment template if .env doesn't exist
if not exist ".env" (
    echo 📋 Creating .env file from template...
    copy .env.example .env
    echo ⚠️  Please edit .env with your AWS credentials and Prometheus URL
)

REM Run setup test
echo 🧪 Running setup validation...
python scripts/test_setup.py

echo.
echo 🎉 Setup complete!
echo.
echo Next steps:
echo 1. Edit .env with your AWS credentials and Prometheus URL
echo 2. Test the collector: python scripts/collect_billing_data.py
echo 3. Push to Prometheus: python scripts/push_to_prometheus.py
echo 4. Set up GitHub Secrets for automated collection
echo.
echo For more information, see README.md

pause