"""
Instagram Business Account API Module
Handles Instagram OAuth, API calls, and webhook processing
"""
import requests
import json
from datetime import datetime, timedelta
from models import db, User
import os
import time
import random


class InstagramAPI:
    def __init__(self, access_token):
        self.access_token = access_token
        self.base_url = "https://graph.instagram.com"
        self.api_version = "v18.0"

    def get_user_profile(self):
        """Get Instagram user profile information"""
        url = f"{self.base_url}/me"
        params = {
            'fields': 'id,username,account_type,media_count,followers_count,follows_count',
            'access_token': self.access_token
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching Instagram profile: {str(e)}")
            return None

    def get_user_media(self, limit=20):
        """Get user's media posts"""
        url = f"{self.base_url}/me/media"
        params = {
            'fields': 'id,caption,media_type,media_url,permalink,timestamp,thumbnail_url,children',
            'access_token': self.access_token,
            'limit': limit
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching Instagram media: {str(e)}")
            return None

    def get_media_comments(self, media_id):
        """Get comments for a specific media post"""
        url = f"{self.base_url}/{media_id}/comments"
        params = {
            'fields': 'id,text,timestamp,username,replies',
            'access_token': self.access_token
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching comments for media {media_id}: {str(e)}")
            return None

    def send_direct_message(self, recipient_id, message):
        """Send direct message to user (requires proper permissions)"""
        # Note: Direct messaging via Instagram Graph API has strict requirements
        # and usually requires business verification and approval
        url = f"https://graph.facebook.com/{self.api_version}/{recipient_id}/messages"
        data = {
            'message': message,
            'access_token': self.access_token
        }
        
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error sending direct message: {str(e)}")
            return None

    def post_comment(self, media_id, comment_text):
        """Post a comment on a media post"""
        url = f"{self.base_url}/{media_id}/comments"
        data = {
            'message': comment_text,
            'access_token': self.access_token
        }
        
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error posting comment on media {media_id}: {str(e)}")
            return None

    def get_account_insights(self):
        """Get account insights (requires proper permissions)"""
        # This requires Instagram Business Account and specific permissions
        url = f"{self.base_url}/me"
        params = {
            'fields': 'account_type,media_count,followers_count,follows_count',
            'access_token': self.access_token
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching account insights: {str(e)}")
            return None


def exchange_short_lived_token(short_lived_token):
    """Exchange short-lived token for long-lived token"""
    url = "https://graph.instagram.com/access_token"
    params = {
        'grant_type': 'ig_exchange_token',
        'client_secret': os.getenv('FB_APP_SECRET'),
        'access_token': short_lived_token
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error exchanging token: {str(e)}")
        return None


def refresh_long_lived_token(user):
    """Refresh long-lived Instagram token if expired"""
    if not user.ig_access_token or not user.fb_access_token:
        return False
    
    try:
        # Instagram tokens can be refreshed using the refresh endpoint
        refresh_url = f"https://graph.instagram.com/refresh_access_token"
        params = {
            'grant_type': 'ig_refresh_token',
            'access_token': user.ig_access_token
        }
        
        response = requests.get(refresh_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'access_token' in data:
            user.ig_access_token = data['access_token']
            expires_in = data.get('expires_in', 5184000)  # Default to 60 days
            user.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            db.session.commit()
            return True
        else:
            print(f"Failed to refresh token: {data}")
            return False
    except requests.RequestException as e:
        print(f"Error refreshing Instagram token: {str(e)}")
        return False


def validate_token(access_token):
    """Validate if Instagram access token is still valid"""
    url = f"https://graph.instagram.com/me"
    params = {
        'fields': 'id,username',
        'access_token': access_token
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return True
        else:
            # Token might be expired or invalid
            error_data = response.json()
            print(f"Token validation failed: {error_data}")
            return False
    except requests.RequestException as e:
            print(f"Error validating token: {str(e)}")
            return False


def get_recent_mentions(user):
    """Get recent mentions and comments for the user"""
    instagram_api = InstagramAPI(user.ig_access_token)
    
    # First get user's recent media
    media_data = instagram_api.get_user_media(limit=10)
    if not media_data:
        return []
    
    mentions = []
    for media in media_data.get('data', []):
        # Get comments for each media
        comments_data = instagram_api.get_media_comments(media['id'])
        if comments_data:
            for comment in comments_data.get('data', []):
                mentions.append({
                    'type': 'comment',
                    'media_id': media['id'],
                    'media_caption': media.get('caption', ''),
                    'comment_id': comment['id'],
                    'username': comment['username'],
                    'text': comment['text'],
                    'timestamp': comment['timestamp']
                })
    
    return mentions


def process_webhook_payload(payload):
    """
    Process Instagram webhook payload
    Called when Instagram sends updates via webhook
    """
    entries = payload.get('entry', [])
    
    for entry in entries:
        changes = entry.get('changes', [])
        
        for change in changes:
            field = change.get('field')
            value = change.get('value', {})
            
            if field == 'instagram_comments':
                # Handle new comments
                process_new_comment(value)
            elif field == 'instagram_mentions':
                # Handle new mentions
                process_new_mention(value)
            elif field == 'instagram_stories':
                # Handle story updates
                process_story_update(value)
            elif field == 'instagram_reels':
                # Handle reel updates
                process_reel_update(value)


def process_new_comment(comment_value):
    """Process new comment notification from webhook"""
    comment_id = comment_value.get('comment_id')
    media_id = comment_value.get('media_id')
    text = comment_value.get('text')
    username = comment_value.get('user_name')
    
    print(f"New comment: {username} commented '{text}' on media {media_id}")


def process_new_mention(mention_value):
    """Process new mention notification from webhook"""
    media_id = mention_value.get('media_id')
    username = mention_value.get('username')
    text = mention_value.get('text')
    
    print(f"New mention: {username} mentioned you in post {media_id}")


def process_story_update(story_value):
    """Process story update notification from webhook"""
    print(f"Story update: {story_value}")


def process_reel_update(reel_value):
    """Process reel update notification from webhook"""
    print(f"Reel update: {reel_value}")


def direct_api_call_with_2fa(username, password, verification_code=None, endpoint=None):
    """
    Make API calls using direct authentication with optional 2FA support
    """
    try:
        from instagrapi import Client
        
        # Add random delay to avoid rate limiting
        time.sleep(random.uniform(2, 5))
        
        cl = Client()
        
        # Set realistic device settings to avoid detection
        cl.set_settings({
            "device_settings": {
                "app_version": "270.0.0.12.117",
                "android_version": "29",
                "android_release": "10",
                "dpi": "640dpi",
                "resolution": "1440x2612",
                "manufacturer": "Samsung",
                "device": "SM-G975F",  # Galaxy S10
                "model": "SM-G975F",
                "cpu": "exynos9820",
                "version_code": "332525302",
            },
            "user_agent": "Instagram 270.0.0.12.117 Android (29/10; 640dpi; 1440x2612; samsung; SM-G975F; SM-G975F; exynos9820; en_US; 332525302)",
            "country": "US",
            "locale": "en_US"
        })
        
        # Add login delay to simulate human behavior
        time.sleep(random.uniform(1, 3))
        
        if verification_code:
            # Login with 2FA verification code
            cl.login(username, password, verification_code=verification_code)
        else:
            # Standard login
            cl.login(username, password)
        
        # Return the client for further operations
        return cl
    except Exception as e:
        # More specific error handling
        error_msg = str(e).lower()
        if 'challenge' in error_msg or 'checkpoint' in error_msg:
            print("Account requires challenge verification. This usually happens with new accounts or suspicious login attempts.")
            print("Solution: Log in manually to Instagram from a web browser or mobile app first, then try again.")
        elif 'login' in error_msg or 'password' in error_msg:
            print("Incorrect username or password.")
        elif 'two-factor' in error_msg or '2fa' in error_msg or 'verification' in error_msg:
            print("Account has two-factor authentication enabled. Verification code required.")
            return "2FA_REQUIRED"
        elif 'rate' in error_msg or 'spam' in error_msg or 'ip' in error_msg or 'blacklist' in error_msg:
            print("Rate limited or IP blocked by Instagram. Try again later from a different IP or wait before attempting again.")
            print("Solution: Wait at least 24 hours before trying again, or use a VPN to change your IP address.")
        elif 'connection' in error_msg or 'timeout' in error_msg:
            print("Connection timeout. Instagram servers may be temporarily unavailable.")
        elif 'suspicious' in error_msg:
            print("Suspicious activity detected. Instagram thinks the login attempt is suspicious.")
            print("Solution: Verify your account by logging in manually to Instagram first.")
        else:
            print(f"Error in direct API call: {str(e)}")
        return None


def direct_api_call(username, password, endpoint, method='GET', data=None):
    """Make API calls using direct authentication with username/password"""
    return direct_api_call_with_2fa(username, password, None, endpoint)


def test_instagram_connection(username, password):
    """
    Test function to verify Instagram connection works properly
    """
    try:
        from instagrapi import Client
        
        # Create client with realistic settings
        cl = Client()
        
        cl.set_settings({
            "device_settings": {
                "app_version": "270.0.0.12.117",
                "android_version": "29",
                "android_release": "10",
                "dpi": "640dpi",
                "resolution": "1440x2612",
                "manufacturer": "Samsung",
                "device": "SM-G975F",
                "model": "SM-G975F",
                "cpu": "exynos9820",
                "version_code": "332525302",
            },
            "user_agent": "Instagram 270.0.0.12.117 Android (29/10; 640dpi; 1440x2612; samsung; SM-G975F; SM-G975F; exynos9820; en_US; 332525302)"
        })
        
        # Add realistic delay before login
        time.sleep(random.uniform(1, 3))
        
        # Try to login
        cl.login(username, password)
        
        # Get user info to verify the connection worked
        user_info = cl.user_info_by_username(username)
        
        print(f"Successfully connected to Instagram account: @{username}")
        print(f"Full name: {user_info.full_name}")
        print(f"Followers: {user_info.follower_count}")
        print(f"Following: {user_info.following_count}")
        
        return cl, user_info
    except Exception as e:
        error_msg = str(e).lower()
        if 'two-factor' in error_msg or '2fa' in error_msg or 'verification' in error_msg:
            print("2FA_REQUIRED")
            return "2FA_REQUIRED", None
        else:
            print(f"Test connection failed: {str(e)}")
            return None, None