# Development Guide

This file provides guidance when working with code in this repository.

## Project Overview

Vitalis Chatbot is a WhatsApp chatbot integration with GoHighLevel (GHL) for appointment scheduling. It uses DeepSeek LLM to process user messages, extract appointment details, and schedule appointments through GHL's API.

## Environment Setup

The project requires a `.env` file with the following environment variables:
```
WEBHOOK_VERIFY_TOKEN=your_webhook_verify_token
GRAPH_API_TOKEN=your_graph_api_token
CALLBACK_URI=your_callback_uri
PORT=5000
DEEPSEEK_API_KEY=your_deepseek_api_key
FIREBASE_CREDENTIALS_PATH=path_to_firebase_credentials.json
GHL_CLIENT_ID=your_ghl_client_id
GHL_CLIENT_SECRET=your_ghl_client_secret
```

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run the Flask server
python app.py
```

## Architecture

The application is structured as follows:

1. **Flask Web Server (`app.py`)**: 
   - Handles WhatsApp webhook integration
   - Manages GoHighLevel OAuth flow
   - Provides account management API endpoints

2. **Firebase Integration**:
   - `firebase/firestore_client.py`: Initializes Firebase connection
   - `firebase/accounts.py`: Manages account configurations
   - `firebase/tokens.py`: Handles OAuth token management
   - `firebase/users.py`: User data management (if available)

3. **Core Functions**:
   - `functions/message_router.py`: Routes incoming messages to appropriate handlers
   - `functions/conversation_handler.py`: Processes conversations using LLM
   - `functions/extract_appointment_info.py`: Uses LLM to extract appointment details
   - `functions/build_confirmation_message.py`: Creates WhatsApp interactive messages
   - `functions/ghl_api.py`: GoHighLevel API integration for appointments

4. **Utilities**:
   - `utils/schemas.py`: Pydantic models for responses
   - `utils/utils.py`: Helper functions for WhatsApp integration

## Message Flow

1. User sends a message to the WhatsApp number
2. Webhook handler receives the message and extracts sender/content
3. Message router identifies the appropriate account configuration
4. Conversation handler processes the message with the LLM
5. If appointment information is detected, confirmation flow is initiated
6. User can confirm the appointment with interactive buttons
7. Confirmed appointments are created in GoHighLevel

## Multi-Account Support

The system supports multiple WhatsApp-to-GHL integrations through a Firestore database:
- Each account has a unique ID and configuration
- WhatsApp numbers are mapped to account IDs
- Each account maintains its own OAuth tokens for GHL
- Custom prompts can be defined per account

## Development Tips

- When working with OAuth flows, use the `/auth` endpoint to initiate authorization
- Test token refreshing with the `/api/accounts/{account_id}/refresh-token` endpoint
- The application stores conversation history in memory (not persisted across restarts)
- Deepseek LLM is used for natural language processing of user messages

## Git Commit Guidelines

- **NEVER include Claude mentions** in commit messages (no "Generated with Claude Code" or "Co-Authored-By: Claude")
- Keep commit messages clean and professional
- Focus on what changed and why, not how it was created