# Firebase Configuration Setup

## Important Security Notice

The `firebase-credentials.json` file contains sensitive service account credentials and has been removed from version control. Never commit this file to git.

## Setup Instructions

### 1. Obtain Firebase Credentials

You need a Firebase service account JSON file. To get one:

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Select your project
3. Go to Project Settings → Service Accounts
4. Click "Generate New Private Key"
5. Save the downloaded file as `firebase-credentials.json`

### 2. Place the Credentials File

Place the `firebase-credentials.json` file in the root of the vitalis-chatbot directory:
```
vitalis-chatbot/
├── firebase-credentials.json  # <-- Place here
├── app.py
├── requirements.txt
└── ...
```

### 3. Verify .gitignore

Ensure `.gitignore` contains:
```
firebase-credentials.json
```

### 4. Environment Variable Alternative (Recommended for Production)

Instead of using a file, you can use an environment variable:

```bash
# Set the environment variable with the JSON content
export FIREBASE_CREDENTIALS='{"type": "service_account", ...}'

# Or point to a file outside the repository
export FIREBASE_CREDENTIALS_PATH='/secure/path/firebase-credentials.json'
```

Then update `app/utils/firebase.py` to use the environment variable:
```python
import os
import json
from firebase_admin import credentials

# Try environment variable first
firebase_creds = os.environ.get('FIREBASE_CREDENTIALS')
if firebase_creds:
    cred = credentials.Certificate(json.loads(firebase_creds))
else:
    # Fall back to file
    cred = credentials.Certificate('firebase-credentials.json')
```

## Security Best Practices

1. **Never commit credentials** - Always check git status before committing
2. **Rotate credentials regularly** - Generate new keys periodically
3. **Use environment variables** - Especially in production
4. **Limit permissions** - Use service accounts with minimal required permissions
5. **Monitor access** - Check Firebase logs for unauthorized access

## Deployment

For deployment environments (Render, Heroku, etc.):

1. Add the Firebase credentials as an environment variable
2. Use the JSON content directly (not the file path)
3. Never include the credentials file in Docker images

## Troubleshooting

If you see errors like:
- `FileNotFoundError: [Errno 2] No such file or directory: 'firebase-credentials.json'`
- `google.auth.exceptions.DefaultCredentialsError`

Make sure:
1. The file exists in the correct location
2. The file has proper permissions (readable by the app)
3. The JSON content is valid

## Team Instructions

All team members must:
1. Delete their local repository
2. Clone fresh: `git clone https://github.com/Vitalis-Stream/vitalis-chatbot-1.0.git`
3. Add their own `firebase-credentials.json` file
4. Never commit this file