#!/usr/bin/env python3
"""
Test script for AWS Billing Data Collector

This script validates the setup and configuration.
"""

import os
import sys
import json
import boto3
import requests
from botocore.exceptions import ClientError, NoCredentialsError

def test_aws_connection():
    """Test AWS connection and permissions"""
    print("🔍 Testing AWS connection...")
    
    try:
        # Test basic AWS connection
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"✅ AWS connection successful")
        print(f"   Account ID: {identity.get('Account', 'N/A')}")
        print(f"   User/Role: {identity.get('Arn', 'N/A')}")
        
        # Test CloudWatch access
        cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
        response = cloudwatch.list_metrics(
            Namespace='AWS/Billing',
            MetricName='EstimatedCharges',
            MaxRecords=1
        )
        print(f"✅ CloudWatch Billing access confirmed")
        
        # Test Cost Explorer access
        ce = boto3.client('ce', region_name='us-east-1')
        ce.get_cost_and_usage(
            TimePeriod={
                'Start': '2024-01-01',
                'End': '2024-01-02'
            },
            Granularity='DAILY',
            Metrics=['BlendedCost']
        )
        print(f"✅ Cost Explorer access confirmed")
        
        return True
        
    except NoCredentialsError:
        print("❌ AWS credentials not found")
        print("   Please configure AWS credentials:")
        print("   - Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        print("   - Or configure AWS CLI with 'aws configure'")
        print("   - Or use IAM roles if running on AWS")
        return False
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDenied':
            print("❌ AWS access denied")
            print("   Please ensure your AWS user/role has the following permissions:")
            print("   - cloudwatch:GetMetricStatistics")
            print("   - cloudwatch:ListMetrics")
            print("   - ce:GetCostAndUsage")
            print("   - budgets:DescribeBudgets")
        else:
            print(f"❌ AWS error: {e}")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected AWS error: {e}")
        return False

def test_prometheus_pushgateway():
    """Test Prometheus Pushgateway connection"""
    print("\n🔍 Testing Prometheus Pushgateway connection...")
    
    pushgateway_url = os.getenv('PROMETHEUS_PUSHGATEWAY_URL')
    if not pushgateway_url:
        print("❌ PROMETHEUS_PUSHGATEWAY_URL not set")
        return False
    
    try:
        # Test health endpoint
        health_url = f"{pushgateway_url.rstrip('/')}/-/healthy"
        response = requests.get(health_url, timeout=5)
        
        if response.status_code == 200:
            print(f"✅ Pushgateway health check passed")
            print(f"   URL: {pushgateway_url}")
            
            # Test pushing a sample metric
            test_metric = """# HELP test_metric A test metric
# TYPE test_metric gauge
test_metric{job="test"} 1.0
"""
            push_url = f"{pushgateway_url.rstrip('/')}/metrics/job/test"
            push_response = requests.post(
                push_url,
                data=test_metric,
                headers={'Content-Type': 'text/plain; version=0.0.4'},
                timeout=10
            )
            
            if push_response.status_code == 200:
                print("✅ Pushgateway metric push test successful")
                
                # Clean up test metric
                requests.delete(push_url, timeout=5)
                return True
            else:
                print(f"❌ Pushgateway push test failed: {push_response.status_code}")
                return False
                
        else:
            print(f"❌ Pushgateway health check failed: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to Pushgateway at {pushgateway_url}")
        print("   Please verify the URL and ensure Pushgateway is running")
        return False
        
    except requests.exceptions.Timeout:
        print(f"❌ Timeout connecting to Pushgateway")
        return False
        
    except Exception as e:
        print(f"❌ Pushgateway test error: {e}")
        return False

def test_environment_variables():
    """Test required environment variables"""
    print("\n🔍 Checking environment variables...")
    
    required_vars = [
        'AWS_REGION',
        'PROMETHEUS_PUSHGATEWAY_URL'
    ]
    
    optional_vars = [
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'AWS_ACCOUNT_ID',
        'PROMETHEUS_JOB_NAME'
    ]
    
    all_good = True
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: Not set (required)")
            all_good = False
    
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            # Hide sensitive values
            if 'SECRET' in var or 'KEY' in var:
                print(f"✅ {var}: {'*' * len(value)}")
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"⚠️  {var}: Not set (optional)")
    
    return all_good

def test_file_structure():
    """Test file structure and permissions"""
    print("\n🔍 Checking file structure...")
    
    required_files = [
        'scripts/collect_billing_data.py',
        'scripts/push_to_prometheus.py',
        'requirements.txt',
        'config/config.yml'
    ]
    
    required_dirs = [
        'data',
        'logs'
    ]
    
    all_good = True
    
    for file_path in required_files:
        if os.path.isfile(file_path):
            print(f"✅ {file_path}: Exists")
        else:
            print(f"❌ {file_path}: Missing")
            all_good = False
    
    for dir_path in required_dirs:
        if os.path.isdir(dir_path):
            print(f"✅ {dir_path}/: Exists")
        else:
            print(f"⚠️  {dir_path}/: Missing (will be created)")
            try:
                os.makedirs(dir_path, exist_ok=True)
                print(f"✅ {dir_path}/: Created")
            except Exception as e:
                print(f"❌ {dir_path}/: Cannot create - {e}")
                all_good = False
    
    return all_good

def main():
    """Run all tests"""
    print("🚀 AWS Billing Data Collector - Setup Validation")
    print("=" * 50)
    
    tests = [
        ("Environment Variables", test_environment_variables),
        ("File Structure", test_file_structure),
        ("AWS Connection", test_aws_connection),
        ("Prometheus Pushgateway", test_prometheus_pushgateway)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} test failed with error: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your setup is ready.")
        return 0
    else:
        print("⚠️  Some tests failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)