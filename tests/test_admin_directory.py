#!/usr/bin/env python3
"""
Test Admin Directory API endpoints
"""

import sys
import json
import requests

# Configuration - EDIT THESE VALUES
BASE_URL = "https://vitalis-chatbot-1-0.onrender.com"
API_KEY = "your-api-key-here"  # Replace with your actual API key
ACCOUNT_ID = "your-account-id-here"  # Replace with a real account ID

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RESET = '\033[0m'

print(f"\n{BLUE}=== Admin Directory API Test ==={RESET}")
print(f"Base URL: {BASE_URL}")
print(f"Account ID: {ACCOUNT_ID}\n")

if API_KEY == "your-api-key-here" or ACCOUNT_ID == "your-account-id-here":
    print(f"{RED}ERROR: Please edit this script and set your API_KEY and ACCOUNT_ID{RESET}")
    print("\nTo get these values:")
    print("1. API_KEY: Check your environment variables or .env file")
    print("2. ACCOUNT_ID: Use an existing account ID from your Firebase")
    sys.exit(1)

headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

# Test 1: Get directory profile (should return empty profile initially)
print(f"{BLUE}1. Getting directory profile for account...{RESET}")
response = requests.get(f"{BASE_URL}/api/accounts/{ACCOUNT_ID}/directory", headers=headers)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print(f"{GREEN}✓ Success{RESET}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}\n")
else:
    print(f"{RED}✗ Failed{RESET}")
    print(f"Response: {response.text}\n")

# Test 2: Update directory profile
print(f"{BLUE}2. Creating/Updating directory profile...{RESET}")
profile_data = {
    "enabled": True,
    "doctor_name": "Dr. Test Doctor",
    "specialty": "cardiology",
    "phone": "+521234567890",
    "email": "test.doctor@example.com",
    "about": "Especialista en cardiología con amplia experiencia",
    "years_experience": 10,
    "consultation_price": 800.0,
    "currency": "MXN",
    "languages": ["Español", "English"],
    "services": ["Consulta general", "Electrocardiograma", "Ecocardiograma"],
    "education": ["Universidad Nacional Autónoma de México", "Hospital General de México"],
    "certifications": ["Consejo Mexicano de Cardiología"],
    "location": {
        "address": "Av. Insurgentes Sur 123",
        "city": "Ciudad de México",
        "state": "CDMX",
        "zip_code": "01234",
        "lat": 19.4326,
        "lng": -99.1332
    }
}

response = requests.put(
    f"{BASE_URL}/api/accounts/{ACCOUNT_ID}/directory",
    headers=headers,
    json=profile_data
)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print(f"{GREEN}✓ Success{RESET}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
else:
    print(f"{RED}✗ Failed{RESET}")
    print(f"Response: {response.text}\n")

# Test 3: Toggle directory status
print(f"{BLUE}3. Enabling directory listing...{RESET}")
response = requests.post(
    f"{BASE_URL}/api/accounts/{ACCOUNT_ID}/directory/toggle",
    headers=headers,
    json={"enabled": True}
)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print(f"{GREEN}✓ Success{RESET}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
else:
    print(f"{RED}✗ Failed{RESET}")
    print(f"Response: {response.text}\n")

# Test 4: Get updated profile
print(f"{BLUE}4. Getting updated profile...{RESET}")
response = requests.get(f"{BASE_URL}/api/accounts/{ACCOUNT_ID}/directory", headers=headers)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print(f"{GREEN}✓ Success{RESET}")
    data = response.json()
    if data.get("success") and data.get("data", {}).get("enabled"):
        print("Profile is now enabled!")
    print(f"Doctor name: {data.get('data', {}).get('doctor_name')}")
    print(f"Specialty: {data.get('data', {}).get('specialty')}\n")
else:
    print(f"{RED}✗ Failed{RESET}")
    print(f"Response: {response.text}\n")

# Test 5: Test public endpoints now that we have data
print(f"{BLUE}5. Testing public doctor search...{RESET}")
response = requests.get(f"{BASE_URL}/api/directory/doctors?page=1&limit=10")
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print(f"{GREEN}✓ Success{RESET}")
    data = response.json()
    print(f"Found {len(data.get('data', []))} doctors")
    if data.get('data'):
        print(f"First doctor: {data['data'][0].get('name')}")
else:
    print(f"{RED}✗ Failed{RESET}")
    print(f"Response: {response.text}\n")

print(f"\n{YELLOW}Next Steps:{RESET}")
print("1. If all tests passed, the backend is working correctly!")
print("2. You can test photo upload with:")
print(f"   curl -X POST {BASE_URL}/api/accounts/{ACCOUNT_ID}/directory/photo \\")
print(f'     -H "X-API-Key: {API_KEY}" \\')
print('     -F "photo=@/path/to/photo.jpg"')
print("\n3. Check Firebase Console:")
print("   - Look for 'directory_profiles' collection")
print("   - Verify the profile was created")
print("\n4. The Admin Hub UI can now be implemented to manage these settings")