#!/usr/bin/env python3
"""
Get account IDs from the API
"""

import requests
import json
import sys

# Configuration
BASE_URL = "https://vitalis-chatbot-1-0.onrender.com"
API_KEY = "your-api-key-here"  # Replace with your actual API key

if API_KEY == "your-api-key-here":
    print("ERROR: Please edit this script and set your API_KEY")
    print("You can find it in your environment variables or .env file")
    sys.exit(1)

headers = {"X-API-Key": API_KEY}

print("Fetching accounts...")
response = requests.get(f"{BASE_URL}/api/accounts", headers=headers)

if response.status_code == 200:
    data = response.json()
    
    # Handle both new and legacy response formats
    if isinstance(data, list):
        # Legacy format
        accounts = data
        print(f"\nFound {len(accounts)} accounts:\n")
        for i, account in enumerate(accounts[:5]):  # Show first 5
            print(f"{i+1}. Account ID: {account.get('account_id', account.get('id', 'Unknown'))}")
            print(f"   Name: {account.get('name', 'No name')}")
            print()
    else:
        # New format
        accounts = data.get('accounts', [])
        print(f"\nFound {len(accounts)} accounts:\n")
        for i, account in enumerate(accounts[:5]):  # Show first 5
            print(f"{i+1}. Account ID: {account.get('id')}")
            print(f"   Name: {account.get('name')}")
            print(f"   Status: {account.get('status')}")
            print()
    
    if len(accounts) > 5:
        print(f"... and {len(accounts) - 5} more accounts")
    
    if accounts:
        print("\nCopy one of these account IDs and use it in the test_admin_directory.py script")
else:
    print(f"Failed to fetch accounts. Status: {response.status_code}")
    print(f"Response: {response.text}")