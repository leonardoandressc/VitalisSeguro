# Vitalis Stream Projects

This repository contains two integrated applications for the Vitalis appointment scheduling system:

1. **Vitalis Chatbot** - WhatsApp chatbot API with GoHighLevel integration
2. **Admin Hub** - Web interface for managing chatbot accounts

## Project Structure

```
vitalis-chatbot-1.0/
├── vitalis-chatbot/       # Backend API (Python/Flask)
│   ├── app/               # Application code (services, models, etc.)
│   ├── tests/             # Test suite
│   ├── API_INTEGRATION_GUIDE.md
│   ├── DEPLOYMENT_GUIDE.md
│   └── COMPLETE_DEPLOYMENT_CHECKLIST.md
└── vitalis-hub/           # Frontend admin interface (Next.js)
    ├── src/               # Source code
    ├── pages/             # API routes
    └── ADMIN_HUB_COMPATIBILITY_UPDATE.md
```

## Quick Start

### Prerequisites

- Python 3.8+ (for chatbot)
- Node.js 18+ (for admin hub)
- Firebase project with Firestore
- WhatsApp Business API access
- GoHighLevel developer account
- DeepSeek API key

### Vitalis Chatbot Setup

```bash
cd vitalis-chatbot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your credentials

# Run the application
python run.py
```

### Admin Hub Setup

```bash
cd vitalis-hub

# Install dependencies
npm install

# Copy environment file
cp .env.example .env.local
# Edit .env.local with your credentials

# Run development server
npm run dev
```

## Architecture Overview

### Vitalis Chatbot (Backend)

- **Technology**: Python, Flask, Firebase, WhatsApp API, GoHighLevel API
- **Purpose**: Process WhatsApp messages and schedule appointments
- **Key Features**:
  - Natural language processing with DeepSeek LLM
  - Multi-tenant support
  - Conversation persistence with Firestore
  - API key authentication
  - Rate limiting
  - Sentry APM integration

### Admin Hub (Frontend)

- **Technology**: Next.js, React, TypeScript, Tailwind CSS
- **Purpose**: Manage accounts and monitor system
- **Key Features**:
  - Account CRUD operations
  - OAuth flow management
  - Secure API proxy
  - JWT authentication

## API Authentication

The Vitalis Chatbot API uses API key authentication:

```bash
curl -H "X-API-Key: your-api-key" https://api.domain.com/api/accounts
```

See [API_INTEGRATION_GUIDE.md](API_INTEGRATION_GUIDE.md) for complete API documentation.

## Deployment

### Vitalis Chatbot (Render)

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Set environment variables from `.env.example`
4. Deploy with:
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn -w 4 -b 0.0.0.0:$PORT "app.main:create_app()"`

### Admin Hub (Render/Vercel)

1. Create a new Static Site or Web Service
2. Connect your GitHub repository
3. Set environment variables from `.env.example`
4. Deploy with:
   - Build: `npm run build`
   - Start: `npm start`

## Security

- API endpoints require authentication via `X-API-Key` header
- Admin hub uses JWT for user authentication
- Conversation data encrypted at rest
- Rate limiting prevents abuse
- CORS configured for secure cross-origin requests

## Environment Variables

### Vitalis Chatbot

```env
# WhatsApp
WEBHOOK_VERIFY_TOKEN=secure_token
GRAPH_API_TOKEN=whatsapp_token

# DeepSeek LLM
DEEPSEEK_API_KEY=deepseek_key

# Firebase
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json

# GoHighLevel
GHL_CLIENT_ID=ghl_client_id
GHL_CLIENT_SECRET=ghl_client_secret

# Security
API_KEYS=key1,key2,key3

# Sentry (Optional)
SENTRY_DSN=sentry_dsn
```

### Admin Hub

```env
# Admin Authentication
AUTH_USERNAME=admin
AUTH_PASSWORD=secure_password
JWT_SECRET=jwt_secret

# Vitalis API
VITALIS_API_KEY=api_key
NEXT_PUBLIC_API_BASE_URL=https://api.domain.com
```

## Development Workflow

1. **Feature Development**:
   - Create feature branch
   - Make changes in appropriate project
   - Test locally with both services running
   - Submit pull request

2. **Testing**:
   - Chatbot: `pytest` (when tests are complete)
   - Admin Hub: `npm test`

3. **Deployment**:
   - Push to main branch
   - Auto-deploy via Render/Vercel

## Status

Both applications are production-ready and fully operational:

### Vitalis Chatbot ✅
- Clean modular architecture (services, repositories, integrations)
- WhatsApp message processing with DeepSeek LLM
- GoHighLevel appointment creation
- Multi-tenant support with Firestore
- API key authentication and rate limiting
- Conversation persistence and management

### Admin Hub ✅
- Modern Next.js App Router architecture
- Account management interface
- GoHighLevel OAuth flow
- Secure API proxy with authentication
- Dark theme with glassmorphism UI

## Support

- API Documentation: See [vitalis-chatbot/API_INTEGRATION_GUIDE.md](vitalis-chatbot/API_INTEGRATION_GUIDE.md)
- Deployment Guide: See [vitalis-chatbot/DEPLOYMENT_GUIDE.md](vitalis-chatbot/DEPLOYMENT_GUIDE.md)
- Deployment Checklist: See [vitalis-chatbot/COMPLETE_DEPLOYMENT_CHECKLIST.md](vitalis-chatbot/COMPLETE_DEPLOYMENT_CHECKLIST.md)
- Admin Hub Compatibility: See [vitalis-hub/ADMIN_HUB_COMPATIBILITY_UPDATE.md](vitalis-hub/ADMIN_HUB_COMPATIBILITY_UPDATE.md)
- Issues: Create GitHub issue

## License

[Your License Here]