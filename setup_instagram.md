# Instagram OAuth Setup Guide

## Prerequisites

1. Facebook Developer Account
2. Instagram Business Account
3. Meta App configured with Instagram Basic Display permissions

## Steps to Configure Instagram OAuth

### 1. Create Meta/Facebook App
1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Create a new app
3. Add "Instagram Basic Display" product to your app

### 2. Configure App Settings
In your Meta app dashboard:

#### Basic Settings:
- Add your website URL to "App Domains"
- Add your redirect URI (e.g., `http://localhost:5000/auth/instagram/callback`) to "Valid OAuth Redirect URIs"

#### Instagram Basic Display Settings:
- Set Deauthorize Callback URL (optional)
- Set Data Deletion Request URL (optional)
- Add Instagram Testers if your app is not approved yet

### 3. Update Environment Variables

Copy the `.env` file values and update with your actual credentials:

```bash
FB_APP_ID=your_actual_app_id
FB_APP_SECRET=your_actual_app_secret
FB_REDIRECT_URI=http://localhost:5000/auth/instagram/callback
WEBHOOK_VERIFY_TOKEN=choose_a_random_string_for_verification
```

### 4. Required Permissions

Your app will request these permissions:
- `instagram_basic` - Read basic Instagram account information
- `instagram_manage_messages` - Manage Instagram messages
- `instagram_manage_comments` - Manage Instagram comments
- `pages_show_list` - Access to pages
- `pages_read_engagement` - Read page engagement
- `pages_messaging` - Send/receive messages via pages

### 5. Webhook Configuration (Optional)

If you want to receive real-time updates from Instagram:

1. Subscribe to these fields in your Meta app:
   - `instagram_comments`
   - `instagram_mentions`

2. Your webhook endpoint will be: `http://yourdomain.com/webhook/instagram`

### 6. Running the Application

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start the application:
```bash
python app.py
```

3. Navigate to your app and click "Connect Instagram" to start the OAuth flow.

## Security Best Practices

- Store `FB_APP_SECRET` securely and never expose it in client-side code
- Use HTTPS in production
- Validate OAuth state parameters to prevent CSRF attacks
- Regularly refresh access tokens
- Implement proper error handling for token expiration

## Troubleshooting

### Common Issues:

1. **Invalid redirect URI**: Make sure your redirect URI exactly matches what's configured in Meta dashboard
2. **Permission errors**: Ensure your Instagram account is added as a tester in the app dashboard
3. **Token expiration**: The app handles automatic token refresh, but ensure your app has the `instagram_basic` permission
4. **Webhook verification failure**: Check that `WEBHOOK_VERIFY_TOKEN` matches between your app and Meta dashboard

### Testing OAuth Locally:
- Use ngrok for local webhook testing: `ngrok http 5000`
- Update your redirect URI and webhook URL accordingly