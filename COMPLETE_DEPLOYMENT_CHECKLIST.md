# Complete Deployment Checklist - Vitalis Chatbot & Admin Hub

## Pre-Deployment Checklist

### 1. Environment Variables Preparation

#### Vitalis Chatbot API
```env
# WhatsApp Configuration
WEBHOOK_VERIFY_TOKEN=<generate-secure-token>
GRAPH_API_TOKEN=<whatsapp-graph-api-token>
CALLBACK_URI=https://your-api-domain.com/callback

# Server Configuration
PORT=5000
DEBUG=false

# DeepSeek LLM Configuration
DEEPSEEK_API_KEY=<your-deepseek-api-key>

# Firebase Configuration
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json

# GoHighLevel OAuth Configuration
GHL_CLIENT_ID=<your-gohl-client-id>
GHL_CLIENT_SECRET=<your-gohl-client-secret>

# Security Configuration
API_KEYS=key1,key2,key3,admin_hub_key  # Important: admin_hub_key will be used by admin hub
ENABLE_RATE_LIMITING=true
RATE_LIMIT_PER_MINUTE=60

# Optional: Sentry APM
SENTRY_DSN=<your-sentry-dsn>
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1

# Conversation Settings
CONVERSATION_TTL_HOURS=24
MAX_CONVERSATION_MESSAGES=100
```

#### Admin Hub
```env
# Admin Authentication
AUTH_USERNAME=admin
AUTH_PASSWORD=<secure-admin-password>
JWT_SECRET=<generate-secure-jwt-secret>

# Vitalis API Configuration
VITALIS_API_KEY=admin_hub_key  # Must match one from API_KEYS above
NEXT_PUBLIC_API_BASE_URL=https://your-api-domain.com

# Next.js Configuration
NEXT_PUBLIC_APP_URL=https://your-admin-domain.com
```

### 2. Generate Secure Tokens
```bash
# Generate API keys
openssl rand -hex 32

# Generate JWT secret
openssl rand -hex 64

# Generate webhook verify token
openssl rand -hex 32
```

## Deployment Steps

### Phase 1: Deploy Vitalis Chatbot API

1. **Create Web Service on Render**
   - [ ] Go to Render Dashboard
   - [ ] Click "New +" → "Web Service"
   - [ ] Connect GitHub repository
   - [ ] Select `vitalis-chatbot` directory

2. **Configure Build Settings**
   - [ ] Name: `vitalis-chatbot-api`
   - [ ] Runtime: `Python 3`
   - [ ] Build Command: `pip install -r requirements.txt`
   - [ ] Start Command: `gunicorn -w 4 -b 0.0.0.0:$PORT "app.main:create_app()"`
   - [ ] Root Directory: `vitalis-chatbot`

3. **Add Environment Variables**
   - [ ] Copy all API environment variables
   - [ ] Ensure all required variables are set
   - [ ] Double-check API_KEYS includes admin_hub_key

4. **Upload Firebase Credentials**
   - [ ] Download Firebase service account JSON
   - [ ] Go to Render "Files" tab
   - [ ] Upload as `firebase-credentials.json`

5. **Deploy API**
   - [ ] Click "Create Web Service"
   - [ ] Wait for deployment to complete
   - [ ] Note the API URL: `https://vitalis-chatbot-api.onrender.com`

### Phase 2: Deploy Admin Hub

1. **Create Second Web Service**
   - [ ] Click "New +" → "Web Service"
   - [ ] Connect same GitHub repository
   - [ ] Select `admin-hub` directory

2. **Configure Build Settings**
   - [ ] Name: `vitalis-admin-hub`
   - [ ] Runtime: `Node`
   - [ ] Build Command: `npm install && npm run build`
   - [ ] Start Command: `npm start`
   - [ ] Root Directory: `admin-hub`

3. **Add Environment Variables**
   - [ ] Set AUTH_USERNAME and AUTH_PASSWORD
   - [ ] Set JWT_SECRET (use generated value)
   - [ ] Set VITALIS_API_KEY to match API_KEYS value
   - [ ] Set NEXT_PUBLIC_API_BASE_URL to API service URL

4. **Deploy Admin Hub**
   - [ ] Click "Create Web Service"
   - [ ] Wait for deployment to complete
   - [ ] Note the admin hub URL

### Phase 3: Configure WhatsApp Integration

1. **Update WhatsApp Webhook**
   - [ ] Use the API URL for webhook: `https://your-api-domain.com/webhook`
   - [ ] Update webhook in Facebook Developer Console
   - [ ] Verify webhook with verification token

2. **Test Webhook**
   ```bash
   curl -X GET "https://your-api-domain.com/webhook?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=test"
   ```

### Phase 4: Post-Deployment Configuration

1. **Access Admin Hub**
   - [ ] Navigate to admin hub URL
   - [ ] Login with AUTH_USERNAME and AUTH_PASSWORD
   - [ ] Verify connection to API (check for "Configuration Error")

2. **Create First Account**
   - [ ] Click "Create Account"
   - [ ] Fill in all required fields
   - [ ] Save account

3. **Configure OAuth**
   - [ ] Click on the account
   - [ ] Click "Authorize with GoHighLevel"
   - [ ] Complete OAuth flow
   - [ ] Verify tokens are saved

## Testing Checklist

### API Testing
- [ ] Health check: `curl https://your-api-domain.com/health`
- [ ] Webhook GET verification works
- [ ] API key authentication works
- [ ] CORS headers are correct

### Admin Hub Testing
- [ ] Login works
- [ ] Account list loads
- [ ] Create new account
- [ ] Update existing account
- [ ] Delete account
- [ ] OAuth flow completes

### Integration Testing
- [ ] Send WhatsApp message
- [ ] Check message appears in logs
- [ ] Test appointment scheduling flow
- [ ] Verify appointment created in GoHighLevel
- [ ] Test conversation persistence

## Monitoring Checklist

### First 24 Hours
- [ ] Monitor Render logs for errors
- [ ] Check WhatsApp webhook delivery status
- [ ] Monitor API response times
- [ ] Verify token refresh is working
- [ ] Check Firestore read/write usage

### Ongoing Monitoring
- [ ] Set up Sentry alerts
- [ ] Monitor rate limiting
- [ ] Track conversation cleanup
- [ ] Monitor memory/CPU usage

## Troubleshooting Common Issues

### Admin Hub Shows "Configuration Error"
1. Check VITALIS_API_KEY is set correctly
2. Verify API_KEYS in API includes the admin hub key
3. Check NEXT_PUBLIC_API_BASE_URL is correct
4. Verify API is running and accessible

### WhatsApp Messages Not Processing
1. Check webhook URL in Facebook Developer Console
2. Verify WEBHOOK_VERIFY_TOKEN matches
3. Check API logs for incoming POST requests
4. Verify GRAPH_API_TOKEN is valid

### OAuth Flow Fails
1. Check GHL_CLIENT_ID and GHL_CLIENT_SECRET
2. Verify CALLBACK_URI matches registered URL
3. Check GoHighLevel app is approved
4. Look for errors in API logs

### API Key Authentication Fails
1. Verify X-API-Key header is being sent
2. Check API_KEYS environment variable
3. Ensure no extra spaces in API keys
4. Check admin hub is using correct key

## Rollback Plan

If issues occur:
1. **For API**: Change start command back to `gunicorn -w 4 -b 0.0.0.0:$PORT app:app`
2. **For Admin Hub**: No changes needed (backward compatible)
3. Redeploy previous commit
4. Monitor that services are working

## Success Criteria

Deployment is successful when:
- [ ] Both services are running without errors
- [ ] Admin hub can manage accounts
- [ ] WhatsApp messages are processed
- [ ] OAuth flow works
- [ ] Appointments are created in GoHighLevel
- [ ] No increase in error rate