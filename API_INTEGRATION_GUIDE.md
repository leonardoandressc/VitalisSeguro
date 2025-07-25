# Vitalis Chatbot API Integration Guide

This guide is designed to help Claude (or developers) integrate new applications with the Vitalis Chatbot API.

## API Overview

The Vitalis Chatbot API is a RESTful API that manages WhatsApp-to-GoHighLevel integrations for appointment scheduling. It provides endpoints for account management, OAuth flows, and webhook handling.

### Base URL
```
Production: https://your-api-domain.com
Development: http://localhost:5000
```

## Authentication

### API Key Authentication

All `/api/*` endpoints require API key authentication using the `X-API-Key` header.

```bash
curl -H "X-API-Key: your-api-key" https://api.domain.com/api/accounts
```

### Obtaining API Keys

API keys are managed by the API administrator. Contact the admin to receive your API key.

## Core Endpoints

### 1. Health Check
```
GET /health
```
No authentication required. Returns service status.

**Response:**
```json
{
  "status": "healthy",
  "service": "vitalis-chatbot",
  "version": "1.0.0"
}
```

### 2. Account Management

#### List All Accounts
```
GET /api/accounts
Headers: X-API-Key: your-api-key
```

**Response:**
```json
{
  "accounts": [
    {
      "id": "account_123",
      "name": "Business Name",
      "phone_number_id": "whatsapp_phone_id",
      "calendar_id": "ghl_calendar_id",
      "location_id": "ghl_location_id",
      "assigned_user_id": "ghl_user_id",
      "custom_prompt": "Custom instructions for AI",
      "status": "active",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### Get Account Details
```
GET /api/accounts/{account_id}
Headers: X-API-Key: your-api-key
```

#### Create Account
```
POST /api/accounts
Headers: 
  X-API-Key: your-api-key
  Content-Type: application/json

Body:
{
  "name": "Business Name",
  "phone_number_id": "whatsapp_phone_id",
  "calendar_id": "ghl_calendar_id",
  "location_id": "ghl_location_id",
  "assigned_user_id": "ghl_user_id",
  "custom_prompt": "Optional custom AI instructions"
}
```

#### Update Account
```
PUT /api/accounts/{account_id}
Headers: 
  X-API-Key: your-api-key
  Content-Type: application/json

Body: (include only fields to update)
{
  "name": "Updated Business Name",
  "custom_prompt": "Updated instructions"
}
```

#### Delete Account
```
DELETE /api/accounts/{account_id}
Headers: X-API-Key: your-api-key
```

### 3. OAuth Flow (GoHighLevel)

#### Initiate OAuth
```
GET /auth?account_id={account_id}
```
Redirects to GoHighLevel OAuth authorization page.

#### OAuth Callback
```
GET /callback
```
Handles OAuth callback from GoHighLevel. Not called directly.

### 4. WhatsApp Webhook

#### Webhook Verification
```
GET /webhook?hub.mode=subscribe&hub.verify_token={token}&hub.challenge={challenge}
```

#### Receive Messages
```
POST /webhook
Headers: (Set by WhatsApp)
Body: WhatsApp webhook payload
```

## Error Handling

### Error Response Format
All errors follow this format:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "additional": "context"
    }
  }
}
```

### Common Error Codes
- `AUTHENTICATION_ERROR` (401) - Invalid or missing API key
- `AUTHORIZATION_ERROR` (403) - Insufficient permissions
- `VALIDATION_ERROR` (400) - Invalid request data
- `RESOURCE_NOT_FOUND` (404) - Resource doesn't exist
- `RATE_LIMIT_EXCEEDED` (429) - Too many requests
- `EXTERNAL_SERVICE_ERROR` (502) - External API failure
- `INTERNAL_ERROR` (500) - Server error

## Rate Limiting

Default rate limits:
- 60 requests per minute per API key
- 100 requests per minute for webhook endpoints

Rate limit headers:
- `X-RateLimit-Limit` - Total allowed requests
- `X-RateLimit-Remaining` - Requests remaining
- `X-RateLimit-Reset` - Unix timestamp when limit resets
- `Retry-After` - Seconds until next request allowed (only on 429)

## Integration Examples

### 1. Node.js/Next.js Integration

```javascript
// lib/vitalis-api.js
const VITALIS_API_URL = process.env.VITALIS_API_URL;
const VITALIS_API_KEY = process.env.VITALIS_API_KEY;

export async function vitalisAPI(endpoint, options = {}) {
  const response = await fetch(`${VITALIS_API_URL}${endpoint}`, {
    ...options,
    headers: {
      'X-API-Key': VITALIS_API_KEY,
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error?.message || 'API request failed');
  }

  return response.json();
}

// Usage
const accounts = await vitalisAPI('/api/accounts');
```

### 2. Python Integration

```python
import os
import requests
from typing import Dict, Any

class VitalisAPI:
    def __init__(self):
        self.base_url = os.getenv('VITALIS_API_URL')
        self.api_key = os.getenv('VITALIS_API_KEY')
        self.headers = {
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json'
        }
    
    def get_accounts(self) -> Dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/api/accounts",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def create_account(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/api/accounts",
            headers=self.headers,
            json=data
        )
        response.raise_for_status()
        return response.json()

# Usage
api = VitalisAPI()
accounts = api.get_accounts()
```

### 3. React Frontend (with Next.js proxy)

```jsx
// hooks/useVitalisAPI.js
import { useState, useCallback } from 'react';

export function useVitalisAPI() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const apiCall = useCallback(async (endpoint, options = {}) => {
    setLoading(true);
    setError(null);
    
    try {
      // Call your Next.js API route that proxies to Vitalis API
      const response = await fetch(`/api${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error?.message || 'Request failed');
      }

      const data = await response.json();
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { apiCall, loading, error };
}

// Usage in component
function AccountList() {
  const { apiCall, loading, error } = useVitalisAPI();
  const [accounts, setAccounts] = useState([]);

  useEffect(() => {
    apiCall('/accounts')
      .then(data => setAccounts(data.accounts))
      .catch(console.error);
  }, []);

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;
  
  return (
    <ul>
      {accounts.map(account => (
        <li key={account.id}>{account.name}</li>
      ))}
    </ul>
  );
}
```

## Best Practices

### 1. Security
- **Never expose API keys** in client-side code
- Use environment variables for configuration
- Implement proxy endpoints in your backend
- Use HTTPS in production

### 2. Error Handling
- Always check response status
- Parse error responses for user-friendly messages
- Implement retry logic for transient failures
- Log errors for debugging

### 3. Performance
- Cache responses when appropriate
- Respect rate limits
- Use pagination for large datasets
- Minimize API calls by batching operations

### 4. Development
- Use different API keys for dev/staging/production
- Test error scenarios
- Monitor API usage
- Keep dependencies updated

## Environment Variables Template

```env
# Vitalis API Configuration
VITALIS_API_URL=https://api.vitalis.com
VITALIS_API_KEY=your_api_key_here

# Optional: Request timeout (ms)
VITALIS_API_TIMEOUT=30000

# Optional: Retry configuration
VITALIS_API_RETRY_ATTEMPTS=3
VITALIS_API_RETRY_DELAY=1000
```

## Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check API key is correct
   - Verify X-API-Key header is sent
   - Ensure API key is active

2. **429 Rate Limited**
   - Implement exponential backoff
   - Check Retry-After header
   - Consider caching responses

3. **CORS Errors**
   - Use server-side proxy
   - Never call API directly from browser
   - Check allowed origins configuration

4. **Connection Timeouts**
   - Implement proper timeout handling
   - Retry with exponential backoff
   - Check network connectivity

## Support

For API access and support:
- Documentation: This guide
- API Status: Check /health endpoint
- Issues: Contact API administrator