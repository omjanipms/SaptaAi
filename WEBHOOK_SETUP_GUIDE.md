# Google Form Webhook Integration Setup Guide

This guide will help you set up automatic triggering of your matrimonial matching system when the Google Form is submitted.

## Overview

The system consists of:
1. **Webhook Server** (`webhook_server.py`) - A Flask server that receives webhook notifications
2. **Google Apps Script** (`google_form_webhook.gs`) - Attached to your Google Form to send webhook notifications
3. **Your existing app.py** - The matrimonial matching logic

## Step 1: Deploy the Webhook Server

### Option A: Local Development (for testing)

1. **Install dependencies:**
   ```bash
   pip install -r webhook_requirements.txt
   ```

2. **Set environment variables:**
   ```bash
   export WEBHOOK_SECRET="your_secret_key_here"
   export PORT=5000
   ```

3. **Run the webhook server:**
   ```bash
   python webhook_server.py
   ```

4. **Test the server:**
   ```bash
   curl http://localhost:5000/health
   ```

### Option B: Cloud Deployment (Recommended for production)

#### Using Heroku:
1. Create a `Procfile`:
   ```
   web: python webhook_server.py
   ```

2. Deploy to Heroku:
   ```bash
   heroku create your-webhook-app
   heroku config:set WEBHOOK_SECRET="your_secret_key_here"
   git push heroku main
   ```

#### Using Railway:
1. Connect your GitHub repository
2. Set environment variables in Railway dashboard
3. Deploy automatically

#### Using Render:
1. Connect your GitHub repository
2. Set build command: `pip install -r webhook_requirements.txt`
3. Set start command: `python webhook_server.py`
4. Set environment variables

### Option C: Using ngrok for local testing with Google Apps Script

1. **Install ngrok:**
   ```bash
   # Download from https://ngrok.com/
   # or use: pip install pyngrok
   ```

2. **Start your local server:**
   ```bash
   python webhook_server.py
   ```

3. **Create ngrok tunnel:**
   ```bash
   ngrok http 5000
   ```

4. **Use the ngrok URL** (e.g., `https://abc123.ngrok.io`) as your webhook URL

## Step 2: Configure Google Apps Script

1. **Open your Google Form:**
   - Go to https://docs.google.com/forms/d/1Hn25v05F0NfyRRv2aCQt236qktrd6rdZJctldHnONUc/edit

2. **Open Script Editor:**
   - Click the three dots menu (⋮) in the top right
   - Select "Script editor"

3. **Replace the default code:**
   - Copy the contents of `google_form_webhook.gs`
   - Paste it into the script editor

4. **Update configuration:**
   ```javascript
   const WEBHOOK_URL = 'https://your-webhook-server.com/webhook'; // Your webhook server URL
   const WEBHOOK_SECRET = 'your_webhook_secret_here'; // Same secret as in your server
   ```

5. **Save the script:**
   - Click "Save" (Ctrl+S)
   - Give it a name like "Matrimonial Form Webhook"

6. **Set up the trigger:**
   - In the script editor, run the `setupFormTrigger()` function
   - Or manually create a trigger:
     - Click on "Triggers" in the left sidebar
     - Click "Add Trigger"
     - Set function: `onFormSubmit`
     - Set event: `From form`
     - Set event type: `On form submit`
     - Click "Save"

## Step 3: Test the Integration

### Test the Webhook Server:
```bash
# Test health endpoint
curl http://your-webhook-server.com/health

# Test status endpoint
curl http://your-webhook-server.com/status

# Test manual trigger
curl -X POST http://your-webhook-server.com/trigger
```

### Test the Google Apps Script:
1. In the Google Apps Script editor, run the `testWebhook()` function
2. Check the execution log for results
3. Check your webhook server logs for the incoming request

### Test the Complete Flow:
1. Submit a test form response
2. Check the webhook server logs
3. Verify that `app.py` processing was triggered
4. Check for email notifications and PDF generation

## Step 4: Monitor and Debug

### Webhook Server Endpoints:
- `GET /` - Server information
- `GET /health` - Health check
- `GET /status` - Processing status
- `POST /webhook` - Webhook endpoint
- `POST /trigger` - Manual trigger

### Logging:
- Check `matrimonial_handler.log` for processing logs
- Check webhook server console output
- Check Google Apps Script execution logs

### Common Issues:

1. **Webhook not receiving requests:**
   - Check if the webhook URL is accessible
   - Verify the webhook secret matches
   - Check Google Apps Script execution logs

2. **Processing not starting:**
   - Check if the webhook server is running
   - Verify the form ID matches
   - Check the spreadsheet ID configuration

3. **Authentication errors:**
   - Verify service account credentials
   - Check if the service account has access to the form/spreadsheet

## Step 5: Production Considerations

### Security:
1. Use HTTPS for your webhook server
2. Set a strong webhook secret
3. Consider IP whitelisting if possible
4. Monitor for unauthorized access

### Reliability:
1. Set up monitoring for the webhook server
2. Implement retry logic for failed webhook deliveries
3. Set up alerts for processing failures
4. Consider using a queue system for high volume

### Scaling:
1. Use a production-grade server (not ngrok)
2. Consider load balancing for multiple instances
3. Implement rate limiting
4. Monitor resource usage

## Troubleshooting

### Webhook Server Issues:
```bash
# Check if server is running
curl http://localhost:5000/health

# Check logs
tail -f matrimonial_handler.log

# Test manual processing
curl -X POST http://localhost:5000/trigger
```

### Google Apps Script Issues:
1. Check execution logs in the script editor
2. Verify trigger is set up correctly
3. Test with `testWebhook()` function
4. Check if the form ID is correct

### Form Integration Issues:
1. Verify the form is connected to the correct spreadsheet
2. Check if the service account has access to both form and spreadsheet
3. Test form submission manually
4. Check spreadsheet for new responses

## Environment Variables

Set these environment variables for your webhook server:

```bash
# Required
WEBHOOK_SECRET=your_secret_key_here
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
ADMIN_EMAIL=admin@example.com

# Optional
PORT=5000
```

## Support

If you encounter issues:
1. Check the logs in `matrimonial_handler.log`
2. Verify all configuration values
3. Test each component individually
4. Check the webhook server status endpoint

## Next Steps

Once the webhook integration is working:
1. Monitor the system for a few days
2. Set up alerts for failures
3. Consider implementing additional features like:
   - Webhook retry logic
   - Processing queue
   - Admin dashboard
   - Analytics and reporting 