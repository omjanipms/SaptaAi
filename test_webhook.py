#!/usr/bin/env python3
"""
Test script for the Matrimonial Webhook Integration
This script tests various aspects of the webhook system.
"""

import requests
import json
import time
import os
from datetime import datetime
import secrets

# Configuration
WEBHOOK_BASE_URL = "http://localhost:5000"  # Change this to your webhook server URL
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", secrets.token_urlsafe(32))

def test_health_endpoint():
    """Test the health endpoint"""
    print("🔍 Testing health endpoint...")
    try:
        response = requests.get(f"{WEBHOOK_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_status_endpoint():
    """Test the status endpoint"""
    print("\n🔍 Testing status endpoint...")
    try:
        response = requests.get(f"{WEBHOOK_BASE_URL}/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status check passed:")
            print(f"   - Is processing: {data.get('is_processing', 'N/A')}")
            print(f"   - Last processed: {data.get('last_processed', 'N/A')}")
            print(f"   - Current submissions: {data.get('current_submission_count', 'N/A')}")
            print(f"   - Last submission count: {data.get('last_submission_count', 'N/A')}")
            return True
        else:
            print(f"❌ Status check failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Status check error: {e}")
        return False

def test_manual_trigger():
    """Test the manual trigger endpoint"""
    print("\n🔍 Testing manual trigger...")
    try:
        response = requests.post(f"{WEBHOOK_BASE_URL}/trigger", timeout=30)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Manual trigger successful: {data}")
            return True
        elif response.status_code == 409:
            print("⚠️  Manual trigger skipped: Processing already in progress")
            return True
        else:
            print(f"❌ Manual trigger failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Manual trigger error: {e}")
        return False

def test_webhook_endpoint():
    """Test the webhook endpoint with a mock form submission"""
    print("\n🔍 Testing webhook endpoint...")
    
    # Create mock webhook data
    mock_webhook_data = {
        "formId": "1Hn25v05F0NfyRRv2aCQt236qktrd6rdZJctldHnONUc",
        "formTitle": "Matrimonial Registration Form",
        "responseId": f"test-response-{int(time.time())}",
        "createTime": datetime.now().isoformat(),
        "submissionData": {
            "timestamp": datetime.now().isoformat(),
            "responseId": f"test-response-{int(time.time())}",
            "responses": {
                "Email": "test@example.com",
                "Full Name": "Test User",
                "Gender": "Male",
                "Birth Date": "1990-01-01",
                "City": "Test City",
                "State": "Test State",
                "Country": "Test Country"
            }
        }
    }
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {WEBHOOK_SECRET}"
        }
        
        response = requests.post(
            f"{WEBHOOK_BASE_URL}/webhook",
            json=mock_webhook_data,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Webhook test successful: {data}")
            return True
        else:
            print(f"❌ Webhook test failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Webhook test error: {e}")
        return False

def test_server_info():
    """Test the server info endpoint"""
    print("\n🔍 Testing server info...")
    try:
        response = requests.get(f"{WEBHOOK_BASE_URL}/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server info:")
            print(f"   - Service: {data.get('service', 'N/A')}")
            print(f"   - Version: {data.get('version', 'N/A')}")
            print(f"   - Form ID: {data.get('form_id', 'N/A')}")
            print(f"   - Spreadsheet ID: {data.get('spreadsheet_id', 'N/A')}")
            return True
        else:
            print(f"❌ Server info failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Server info error: {e}")
        return False

def test_google_sheets_connection():
    """Test the Google Sheets connection"""
    print("\n🔍 Testing Google Sheets connection...")
    try:
        # Import the function from app.py
        from app import fetch_data_from_google_sheets
        
        df = fetch_data_from_google_sheets()
        if df is not None and not df.empty:
            print(f"✅ Google Sheets connection successful:")
            print(f"   - Rows retrieved: {len(df)}")
            print(f"   - Columns: {len(df.columns)}")
            return True
        else:
            print("❌ Google Sheets connection failed: No data retrieved")
            return False
    except Exception as e:
        print(f"❌ Google Sheets connection error: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("🧪 Matrimonial Webhook Integration Tests")
    print("=" * 60)
    
    tests = [
        ("Server Info", test_server_info),
        ("Health Endpoint", test_health_endpoint),
        ("Status Endpoint", test_status_endpoint),
        ("Google Sheets Connection", test_google_sheets_connection),
        ("Manual Trigger", test_manual_trigger),
        ("Webhook Endpoint", test_webhook_endpoint),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📈 Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! Your webhook integration is working correctly.")
    else:
        print("⚠️  Some tests failed. Please check the configuration and try again.")
    
    return failed == 0

if __name__ == "__main__":
    # Check if webhook server is running
    try:
        response = requests.get(f"{WEBHOOK_BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("❌ Webhook server is not running or not accessible.")
            print(f"Please start the webhook server first:")
            print(f"python start_webhook.py")
            exit(1)
    except:
        print("❌ Cannot connect to webhook server.")
        print(f"Please start the webhook server first:")
        print(f"python start_webhook.py")
        exit(1)
    
    # Run tests
    success = run_all_tests()
    exit(0 if success else 1) 