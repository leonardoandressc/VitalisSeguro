#!/usr/bin/env python3
"""
Test script for Directory Management API
Usage: python test_directory_api.py [--local]
"""

import sys
import json
import requests
from datetime import datetime

# Configuration
LOCAL = "--local" in sys.argv
BASE_URL = "http://localhost:5000" if LOCAL else "https://vitalis-chatbot-1-0.onrender.com"
API_KEY = "your-api-key-here"  # Replace with your actual API key
ACCOUNT_ID = "test-account-id"  # Replace with an actual account ID

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RESET = '\033[0m'

print(f"\n{BLUE}=== Directory Management API Test ==={RESET}")
print(f"Testing {'LOCAL' if LOCAL else 'REMOTE (Render)'} environment")
print(f"Base URL: {BASE_URL}\n")

def test_endpoint(method, endpoint, data=None, description="", files=None):
    """Test an API endpoint and print results"""
    print(f"{BLUE}Testing: {description}{RESET}")
    print(f"Endpoint: {method} {endpoint}")
    
    headers = {"X-API-Key": API_KEY}
    if data and not files:
        headers["Content-Type"] = "application/json"
    
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            if files:
                response = requests.post(url, headers=headers, files=files)
            else:
                response = requests.post(url, headers=headers, json=data)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=data)
        else:
            print(f"{RED}Unsupported method: {method}{RESET}")
            return
        
        if response.status_code >= 200 and response.status_code < 300:
            print(f"{GREEN}✓ Success (Status: {response.status_code}){RESET}")
        else:
            print(f"{RED}✗ Failed (Status: {response.status_code}){RESET}")
        
        # Pretty print JSON response
        try:
            json_response = response.json()
            print("Response:", json.dumps(json_response, indent=2))
        except:
            print("Response:", response.text)
            
    except requests.exceptions.ConnectionError:
        print(f"{RED}✗ Connection Error - Is the server running?{RESET}")
    except Exception as e:
        print(f"{RED}✗ Error: {str(e)}{RESET}")
    
    print("\n" + "-" * 50 + "\n")

# Run tests
if __name__ == "__main__":
    # 1. Get directory profile (should return empty profile if none exists)
    test_endpoint(
        "GET", 
        f"/api/accounts/{ACCOUNT_ID}/directory",
        description="Get directory profile for account"
    )
    
    # 2. Get specialties options
    test_endpoint(
        "GET",
        "/api/directory/specialties",
        description="Get list of medical specialties"
    )
    
    # 3. Update directory profile
    profile_data = {
        "enabled": True,
        "doctor_name": "Dr. María González",
        "specialty": "cardiology",
        "phone": "+521234567890",
        "email": "maria.gonzalez@example.com",
        "about": "Especialista en cardiología con 15 años de experiencia",
        "years_experience": 15,
        "consultation_price": 800.0,
        "currency": "MXN",
        "languages": ["Español", "English"],
        "services": ["Consulta general", "Electrocardiograma", "Ecocardiograma"],
        "education": ["Universidad Nacional Autónoma de México", "Hospital General de México"],
        "certifications": ["Consejo Mexicano de Cardiología"],
        "insurance_accepted": ["Seguros Monterrey", "AXA", "MetLife"],
        "location": {
            "address": "Av. Insurgentes Sur 123",
            "city": "Ciudad de México",
            "state": "CDMX",
            "zip_code": "01234",
            "lat": 19.4326,
            "lng": -99.1332
        },
        "schedule": {
            "monday": {"start": "09:00", "end": "17:00"},
            "tuesday": {"start": "09:00", "end": "17:00"},
            "wednesday": {"start": "09:00", "end": "17:00"},
            "thursday": {"start": "09:00", "end": "17:00"},
            "friday": {"start": "09:00", "end": "14:00"}
        }
    }
    
    test_endpoint(
        "PUT",
        f"/api/accounts/{ACCOUNT_ID}/directory",
        data=profile_data,
        description="Update directory profile"
    )
    
    # 4. Toggle directory status
    test_endpoint(
        "POST",
        f"/api/accounts/{ACCOUNT_ID}/directory/toggle",
        data={"enabled": True},
        description="Enable directory listing"
    )
    
    # 5. Search doctors (public endpoint - no API key needed)
    test_endpoint(
        "GET",
        "/api/directory/doctors?specialty=cardiology&lat=19.4326&lng=-99.1332&page=1&limit=10",
        description="Search doctors (public endpoint)"
    )
    
    # 6. Get all specialties with counts
    test_endpoint(
        "GET",
        "/api/directory/specialties",
        description="Get specialties list with doctor counts"
    )
    
    print(f"{YELLOW}Photo Upload Test:{RESET}")
    print("To test photo upload, you can use curl:")
    print(f"curl -X POST {BASE_URL}/api/accounts/{ACCOUNT_ID}/directory/photo \\")
    print(f'  -H "X-API-Key: {API_KEY}" \\')
    print('  -F "photo=@/path/to/your/photo.jpg"')
    print("\nOr modify this script to include a test image file.")
    
    print(f"\n{YELLOW}Important Notes:{RESET}")
    print("1. Replace 'your-api-key-here' with your actual API key")
    print("2. Replace 'test-account-id' with a real account ID from your system")
    print("3. The backend deployment on Render may take a few minutes")
    print("4. Check Firebase Console for:")
    print("   - New 'directory_profiles' collection in Firestore")
    print("   - Uploaded photos in Storage under 'directory/{account_id}/'")
    
    print(f"\n{BLUE}=== Test Complete ==={RESET}\n")