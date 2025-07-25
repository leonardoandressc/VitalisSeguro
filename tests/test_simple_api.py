#!/usr/bin/env python3
"""
Simple test for directory API endpoints
"""

import requests
import json

BASE_URL = "https://vitalis-chatbot-1-0.onrender.com"

print("Testing Directory API Endpoints...\n")

# Test 1: Health check
print("1. Testing health endpoint...")
response = requests.get(f"{BASE_URL}/health")
print(f"Status: {response.status_code}")
print(f"Response: {response.text}\n")

# Test 2: Specialties (public endpoint)
print("2. Testing specialties endpoint...")
response = requests.get(f"{BASE_URL}/api/directory/specialties")
print(f"Status: {response.status_code}")
try:
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
except:
    print(f"Response: {response.text}")
print()

# Test 3: Search doctors (public endpoint)
print("3. Testing doctors search endpoint...")
response = requests.get(f"{BASE_URL}/api/directory/doctors?page=1&limit=10")
print(f"Status: {response.status_code}")
try:
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
except:
    print(f"Response: {response.text}")
print()

print("\nIf you see 500 errors, the deployment might still be in progress.")
print("Wait 2-3 minutes and try again.")