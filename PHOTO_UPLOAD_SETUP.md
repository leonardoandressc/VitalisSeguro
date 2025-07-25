# Photo Upload Setup Guide

To enable photo uploads for doctor profiles, you need to complete the following setup:

## Backend Requirements

1. **Install Google Cloud Storage**
   ```bash
   pip install google-cloud-storage
   ```

2. **Configure Firebase Storage**
   - Ensure your Firebase credentials JSON file includes Storage permissions
   - The service account needs Storage Admin or Storage Object Admin role

3. **Initialize Storage Bucket**
   - In Firebase Console, create a Storage bucket if not already created
   - Note the bucket name (usually `your-project-id.appspot.com`)

## Admin Hub Requirements

For the Admin Hub proxy endpoint to handle file uploads:

1. **Install formidable**
   ```bash
   npm install formidable
   npm install @types/formidable --save-dev
   ```

2. **Update the photo upload proxy endpoint**
   The `/pages/api/accounts/[account_id]/directory/photo.js` endpoint needs to:
   - Parse multipart form data
   - Forward the file to the backend API
   - Handle the response

## Testing Photo Upload

1. Enable directory for a doctor account
2. Click "Upload Photo" in the Directory tab
3. Select an image (JPG, PNG, or WebP, max 5MB)
4. The photo should upload and display immediately

## Troubleshooting

- If you get a 501 error, the backend dependencies are not installed
- Check Firebase Storage rules allow authenticated uploads
- Verify the service account has proper Storage permissions
- Check the backend logs for specific error messages