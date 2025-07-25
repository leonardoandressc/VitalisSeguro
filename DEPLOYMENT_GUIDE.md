# Deployment Guide

This guide provides step-by-step instructions for deploying both the Vitalis Chatbot API and Admin Hub.

## Prerequisites

1. **Firebase Project**: With Firestore enabled
2. **WhatsApp Business API**: Access token and phone number ID
3. **GoHighLevel Account**: Client ID and secret for OAuth
4. **DeepSeek API**: API key for LLM functionality
5. **Render Account**: For hosting both applications
6. **Domain Names** (optional): For custom URLs

## Environment Variables

### Vitalis Chatbot API

Create these environment variables in Render:

```env
# WhatsApp Configuration
WEBHOOK_VERIFY_TOKEN=your_secure_webhook_verify_token
GRAPH_API_TOKEN=your_whatsapp_graph_api_token
CALLBACK_URI=https://your-api-domain.com/callback

# Server Configuration
PORT=5000
DEBUG=false

# DeepSeek LLM Configuration
DEEPSEEK_API_KEY=your_deepseek_api_key

# Firebase Configuration
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json

# GoHighLevel OAuth Configuration
GHL_CLIENT_ID=your_gohl_client_id
GHL_CLIENT_SECRET=your_ghl_client_secret

# Security Configuration
API_KEYS=key1,key2,key3,admin_hub_key
ENABLE_RATE_LIMITING=true
RATE_LIMIT_PER_MINUTE=60

# Sentry APM Configuration (Optional)
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1

# Conversation Settings
CONVERSATION_TTL_HOURS=24
MAX_CONVERSATION_MESSAGES=100
```

### Admin Hub

Create these environment variables in Render:

```env
# Admin Authentication
AUTH_USERNAME=admin
AUTH_PASSWORD=your_secure_admin_password
JWT_SECRET=your_secure_jwt_secret

# Vitalis API Configuration
VITALIS_API_KEY=admin_hub_key  # Must match one from API_KEYS above
NEXT_PUBLIC_API_BASE_URL=https://your-api-domain.com

# Next.js Configuration
NEXT_PUBLIC_APP_URL=https://your-admin-domain.com
```

## Step-by-Step Deployment

### 1. Deploy Vitalis Chatbot API

1. **Create Web Service on Render**:
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Select the `vitalis-chatbot` directory

2. **Configure Build Settings**:
   - **Name**: `vitalis-chatbot-api`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -w 4 -b 0.0.0.0:$PORT "app.main:create_app()"`
   - **Root Directory**: `vitalis-chatbot`
   - **NOTE**: The new refactored system uses `app.main:create_app()` instead of `app:app`

3. **Add Environment Variables**:
   - Copy all variables from the list above
   - Generate secure API keys using: `openssl rand -hex 32`

4. **Upload Firebase Credentials**:
   - Download your Firebase service account JSON
   - In Render, go to "Files" tab
   - Upload the JSON file as `firebase-credentials.json`

5. **Deploy**:
   - Click "Create Web Service"
   - Wait for deployment to complete
   - Note the service URL (e.g., `https://vitalis-chatbot-api.onrender.com`)

### 2. Deploy Admin Hub

1. **Create Web Service on Render**:
   - Click "New +" → "Web Service"
   - Connect the same GitHub repository
   - Select the `admin-hub` directory

2. **Configure Build Settings**:
   - **Name**: `vitalis-admin-hub`
   - **Runtime**: `Node`
   - **Build Command**: `npm install && npm run build`
   - **Start Command**: `npm start`
   - **Root Directory**: `admin-hub`

3. **Add Environment Variables**:
   - Use the admin hub variables listed above
   - Set `NEXT_PUBLIC_API_BASE_URL` to your API service URL
   - **IMPORTANT**: The `VITALIS_API_KEY` must match one of the keys in the API's `API_KEYS` list

4. **Deploy**:
   - Click "Create Web Service"
   - Wait for deployment to complete
   - Note the admin hub URL

### 3. Configure WhatsApp Webhook

1. **Set Webhook URL**:
   ```bash
   curl -X POST "https://graph.facebook.com/v18.0/YOUR_PHONE_NUMBER_ID/webhooks" \
     -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "webhook_url": "https://your-api-domain.com/webhook",
       "verify_token": "your_webhook_verify_token"
     }'
   ```

2. **Subscribe to Message Events**:
   ```bash
   curl -X POST "https://graph.facebook.com/v18.0/YOUR_APP_ID/subscriptions" \
     -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "object": "whatsapp_business_account",
       "callback_url": "https://your-api-domain.com/webhook",
       "verify_token": "your_webhook_verify_token",
       "fields": "messages"
     }'
   ```

### 4. Test the Deployment

1. **Test API Health**:
   ```bash
   curl https://your-api-domain.com/health
   ```

2. **Test Admin Hub Access**:
   - Visit your admin hub URL
   - Log in with the admin credentials
   - Try creating a test account

3. **Test WhatsApp Integration**:
   - Send a test message to your WhatsApp number
   - Check Render logs for message processing

## Post-Deployment Configuration

### 1. Create Your First Account

1. Access the admin hub
2. Create an account with:
   - Name: Your business name
   - Phone Number ID: From WhatsApp Business API
   - Calendar/Location/User IDs: From GoHighLevel

### 2. Set Up OAuth

1. In the admin hub, click on your account
2. Click "Authorize with GoHighLevel"
3. Complete the OAuth flow
4. Verify tokens are saved

### 3. Test Appointment Flow

1. Send a message to your WhatsApp number
2. Try scheduling an appointment
3. Verify it appears in GoHighLevel

## Monitoring and Maintenance

### 1. Set Up Monitoring

- **Render Logs**: Monitor application logs
- **Sentry**: Track errors and performance
- **WhatsApp Webhooks**: Monitor webhook delivery

### 2. Regular Maintenance

- **Token Refresh**: GoHighLevel tokens expire, monitor refresh
- **Conversation Cleanup**: Automatic but monitor Firestore usage
- **Rate Limiting**: Adjust limits based on usage

### 3. Scaling

- **API**: Increase Render plan for more CPU/memory
- **Database**: Monitor Firestore read/write limits
- **Admin Hub**: Can handle multiple administrators

## Troubleshooting

### Common Issues

1. **"Configuration Error" in Admin Hub**:
   - Check `VITALIS_API_KEY` is set and matches API
   - Verify `NEXT_PUBLIC_API_BASE_URL` is correct

2. **WhatsApp Messages Not Processing**:
   - Check webhook URL is reachable
   - Verify `WEBHOOK_VERIFY_TOKEN` matches
   - Check Render logs for errors

3. **GoHighLevel Authorization Fails**:
   - Verify `GHL_CLIENT_ID` and `GHL_CLIENT_SECRET`
   - Check `CALLBACK_URI` matches exactly
   - Ensure GoHighLevel app is approved

4. **Firebase Connection Issues**:
   - Verify `firebase-credentials.json` is uploaded
   - Check Firestore is enabled in Firebase project
   - Verify service account permissions

### Log Analysis

**API Logs** (useful for debugging):
```bash
# In Render dashboard, go to your API service logs
# Look for structured JSON logs with request_id for tracing
```

**Admin Hub Logs** (for frontend issues):
```bash
# Check browser console for errors
# Check Render deployment logs for build issues
```

## Security Checklist

- [ ] API keys are secure and rotated regularly
- [ ] Admin password is strong
- [ ] HTTPS is enabled (automatic with Render)
- [ ] Firebase rules are properly configured
- [ ] GoHighLevel permissions are minimal
- [ ] Sentry doesn't log sensitive data
- [ ] Rate limiting is enabled

## Performance Optimization

1. **API Response Times**:
   - Monitor with Sentry APM
   - Optimize database queries
   - Consider caching frequently accessed data

2. **Admin Hub**:
   - Enable Next.js optimizations
   - Monitor bundle size
   - Use CDN for static assets

3. **WhatsApp Processing**:
   - Keep webhook responses under 20 seconds
   - Use async processing for complex operations
   - Monitor message queue if volume is high