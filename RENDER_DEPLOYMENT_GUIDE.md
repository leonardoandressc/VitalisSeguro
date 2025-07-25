# Render.com Deployment Guide for Appointment Reminders

This guide walks you through setting up the appointment reminder cron job on Render.com.

## Prerequisites

1. Active Render.com account
2. GitHub repository connected to Render
3. All required environment variables from your `.env` file

## Step-by-Step Setup

### 1. Create New Cron Job

1. Log into [Render Dashboard](https://dashboard.render.com)
2. Click **"New +"** → **"Cron Job"**
3. Connect your GitHub repository if not already connected

### 2. Configure Basic Settings

Fill in the following configuration:

| Setting | Value |
|---------|-------|
| **Name** | `vitalis-appointment-reminders` |
| **Region** | Oregon (US West) or closest to your users |
| **Branch** | `main` |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Command** | `python run_reminder_job.py --timezone America/Los_Angeles` |

### 3. Set Schedule

For daily reminders at 8:00 AM PST:

| Setting | Value | Description |
|---------|-------|-------------|
| **Schedule** | `0 15 * * *` | 8 AM PST = 3 PM UTC |

**Other common schedules:**
- 9 AM PST: `0 16 * * *`
- 7 AM PST: `0 14 * * *`
- 8 AM EST: `0 13 * * *`

**Schedule format (cron syntax):**
```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6)
│ │ │ │ │
* * * * *
```

### 4. Configure Environment Variables

Add all required environment variables:

```bash
# Firebase Configuration
FIREBASE_CREDENTIALS_PATH=firebase-credentials.json

# WhatsApp Business API
GRAPH_API_TOKEN=your_whatsapp_api_token

# GoHighLevel API
GHL_CLIENT_ID=your_ghl_client_id
GHL_CLIENT_SECRET=your_ghl_client_secret
GHL_API_BASE_URL=https://services.leadconnectorhq.com

# Application Settings
WEBHOOK_VERIFY_TOKEN=your_webhook_verify_token
DEEPSEEK_API_KEY=your_deepseek_api_key
TIMEZONE=America/Los_Angeles
CONVERSATION_TTL_HOURS=24
DEBUG=false
TESTING=false
```

### 5. Add Firebase Credentials

Since Render doesn't support file uploads directly, you need to add Firebase credentials as an environment variable:

1. Convert your `firebase-credentials.json` to base64:
   ```bash
   base64 -i firebase-credentials.json | tr -d '\n'
   ```

2. Add as environment variable:
   - Name: `FIREBASE_CREDENTIALS_BASE64`
   - Value: [paste the base64 string]

3. Update `run_reminder_job.py` to decode the credentials:
   ```python
   import base64
   import json
   
   # Get credentials from environment
   creds_base64 = os.environ.get('FIREBASE_CREDENTIALS_BASE64')
   if creds_base64:
       creds_json = base64.b64decode(creds_base64).decode('utf-8')
       with open('firebase-credentials.json', 'w') as f:
           f.write(creds_json)
   ```

### 6. Select Instance Type

For the reminder job, the free tier should be sufficient:

| Setting | Recommendation |
|---------|----------------|
| **Instance Type** | Free (512 MB RAM) |
| **Upgrade if** | Processing > 50 accounts or > 500 daily appointments |

### 7. Deploy

1. Click **"Create Cron Job"**
2. Wait for the initial build to complete
3. Check the logs to ensure no errors

## Testing Your Deployment

### 1. Manual Trigger

You can manually trigger the cron job from Render dashboard:
1. Go to your cron job
2. Click **"Trigger Run"**
3. Check logs for execution

### 2. Test with Dry Run

Temporarily change the command to include dry-run:
```bash
python run_reminder_job.py --timezone America/Los_Angeles --dry-run
```

### 3. Monitor Logs

Check logs regularly to ensure reminders are being sent:
- Look for "Reminder job completed" messages
- Check error count
- Verify reminders_sent count

## Monitoring and Alerts

### 1. Set Up Notifications

In Render dashboard:
1. Go to **Settings** → **Notifications**
2. Enable email alerts for:
   - Failed runs
   - Successful runs (optional)

### 2. Check Firestore Collections

Monitor these collections in Firebase Console:
- `appointment_reminders`: Sent reminders
- `reminder_job_runs`: Job execution history
- `confirmed_appointments`: Upcoming appointments

### 3. Create Monitoring Dashboard

Use Firebase Console to create queries:
```javascript
// Today's reminders sent
db.collection('appointment_reminders')
  .where('sent_at', '>=', todayStart)
  .where('sent_at', '<=', todayEnd)

// Failed job runs
db.collection('reminder_job_runs')
  .where('errors', '!=', [])
  .orderBy('timestamp', 'desc')
  .limit(10)
```

## Troubleshooting

### Common Issues

1. **"No active accounts found"**
   - Verify accounts in Firestore have `status: "active"`
   - Check account has valid `phone_number_id`

2. **"Failed to send WhatsApp message"**
   - Verify `GRAPH_API_TOKEN` is valid
   - Check WhatsApp phone number is registered
   - Ensure recipient phone format is correct

3. **"Token refresh failed"**
   - GHL tokens may be expired
   - Re-authenticate through OAuth flow

4. **No appointments found**
   - Check timezone settings
   - Verify appointments exist for today
   - Check Firestore composite indexes

### Debug Mode

Add logging environment variable for more details:
```bash
LOG_LEVEL=DEBUG
```

### Performance Optimization

If processing many accounts:

1. **Increase instance size** to 1GB or 2GB RAM
2. **Add parallel processing** (modify code to process accounts concurrently)
3. **Split into multiple jobs** by account groups

## Security Best Practices

1. **Rotate API tokens** regularly
2. **Use least privilege** for Firebase service account
3. **Monitor for unusual activity** in logs
4. **Set up alerts** for failed authentications

## Cost Estimation

| Accounts | Daily Appointments | Recommended Tier | Monthly Cost |
|----------|-------------------|------------------|--------------|
| 1-10 | < 50 | Free | $0 |
| 10-50 | 50-200 | Starter | $7 |
| 50+ | 200+ | Standard | $25 |

## Support

For issues:
1. Check Render status page
2. Review application logs
3. Verify environment variables
4. Test with `test_reminder.py` locally

## Next Steps

1. Set up monitoring dashboard
2. Configure alerts
3. Plan for scaling
4. Document customer feedback