#!/bin/bash

# Test script for Directory Management API
# Usage: ./test-directory-api.sh [local|remote]

# Configuration
if [ "$1" = "local" ]; then
    BASE_URL="http://localhost:5000"
    echo "Testing LOCAL environment"
else
    BASE_URL="https://vitalis-chatbot-1-0.onrender.com"
    echo "Testing REMOTE environment (Render)"
fi

# Replace with your actual API key
API_KEY="your-api-key-here"

# Test account ID - replace with an actual account ID
ACCOUNT_ID="test-account-id"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "\n${BLUE}=== Directory Management API Test ===${NC}\n"

# Function to test an endpoint
test_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local description=$4
    
    echo -e "${BLUE}Testing: $description${NC}"
    echo "Endpoint: $method $endpoint"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" -X GET \
            -H "X-API-Key: $API_KEY" \
            "$BASE_URL$endpoint")
    elif [ "$method" = "PUT" ] || [ "$method" = "POST" ]; then
        response=$(curl -s -w "\n%{http_code}" -X $method \
            -H "X-API-Key: $API_KEY" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$BASE_URL$endpoint")
    fi
    
    # Extract status code and body
    status_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$status_code" -ge 200 ] && [ "$status_code" -lt 300 ]; then
        echo -e "${GREEN}✓ Success (Status: $status_code)${NC}"
    else
        echo -e "${RED}✗ Failed (Status: $status_code)${NC}"
    fi
    
    echo "Response: $body"
    echo -e "\n---\n"
}

# 1. Test getting directory profile (should return empty profile if none exists)
test_endpoint "GET" "/api/accounts/$ACCOUNT_ID/directory" "" \
    "Get directory profile for account"

# 2. Test getting specialties options
test_endpoint "GET" "/api/directory/specialties" "" \
    "Get list of medical specialties"

# 3. Test updating directory profile
profile_data='{
    "enabled": true,
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
    "location": {
        "address": "Av. Insurgentes Sur 123",
        "city": "Ciudad de México",
        "state": "CDMX",
        "zip_code": "01234",
        "lat": 19.4326,
        "lng": -99.1332
    }
}'

test_endpoint "PUT" "/api/accounts/$ACCOUNT_ID/directory" "$profile_data" \
    "Update directory profile"

# 4. Test toggling directory status
toggle_data='{"enabled": true}'
test_endpoint "POST" "/api/accounts/$ACCOUNT_ID/directory/toggle" "$toggle_data" \
    "Enable directory listing"

# 5. Test public doctor search
test_endpoint "GET" "/api/directory/doctors?specialty=cardiology&lat=19.4326&lng=-99.1332&page=1&limit=10" "" \
    "Search doctors (public endpoint)"

# 6. Test getting specific doctor (if profile was created)
# This will only work if the profile was successfully created above
if [ "$ACCOUNT_ID" != "test-account-id" ]; then
    # Get the profile to find its ID
    profile_response=$(curl -s -X GET \
        -H "X-API-Key: $API_KEY" \
        "$BASE_URL/api/accounts/$ACCOUNT_ID/directory")
    
    # Try to extract profile ID (this is a simple approach, might need adjustment)
    profile_id=$(echo "$profile_response" | grep -o '"id":"[^"]*"' | sed 's/"id":"//' | sed 's/"//')
    
    if [ ! -z "$profile_id" ]; then
        test_endpoint "GET" "/api/directory/doctors/$profile_id" "" \
            "Get specific doctor details (public endpoint)"
    fi
fi

echo -e "${BLUE}=== Test Complete ===${NC}\n"
echo "Note: To test photo upload, use:"
echo "curl -X POST $BASE_URL/api/accounts/$ACCOUNT_ID/directory/photo \\"
echo "  -H \"X-API-Key: $API_KEY\" \\"
echo "  -F \"photo=@/path/to/your/photo.jpg\""