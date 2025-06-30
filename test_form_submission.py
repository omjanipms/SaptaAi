#!/usr/bin/env python3
"""
Test script to simulate a Google Form submission
"""

import requests
import json
import time

# Configuration
WEBHOOK_URL = "https://25e8-2405-201-2021-5855-8188-97f9-1f91-f300.ngrok-free.app/webhook"
WEBHOOK_SECRET = "wf_cRjcXgo1RfUuuYtoOyS6RTiiLCs31dZCKLCNTbRk"

def test_webhook():
    """Test the webhook endpoint"""
    print("🧪 Testing webhook endpoint...")
    
    # Simulate form submission data
    test_data = {
        "timestamp": "2025-06-29T20:30:00Z",
        "response_id": "test_response_123",
        "form_data": {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "1234567890"
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {WEBHOOK_SECRET}"
    }
    
    try:
        print(f"📤 Sending test data to: {WEBHOOK_URL}")
        response = requests.post(WEBHOOK_URL, json=test_data, headers=headers, timeout=30)
        
        print(f"📥 Response Status: {response.status_code}")
        print(f"📥 Response Body: {response.text}")
        
        if response.status_code == 200:
            print("✅ Webhook test successful!")
            return True
        else:
            print("❌ Webhook test failed!")
            return False
            
    except Exception as e:
        print(f"❌ Error testing webhook: {e}")
        return False

if __name__ == "__main__":
    test_webhook() 