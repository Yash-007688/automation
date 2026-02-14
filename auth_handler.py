"""
Instagram Authentication Handler
Handles direct communication with Instagram's authentication servers
"""

import requests
import json
import os
from instagrapi import Client
from instagrapi.exceptions import (
    BadCredentials, 
    TwoFactorRequired, 
    ChallengeRequired, 
    LoginRequired,
    PleaseWaitFewMinutes,
    RateLimitError
)
import time
import random
from typing import Optional, Tuple, Dict, Any


class InstagramAuthHandler:
    """
    Handles authentication with Instagram's servers directly
    """
    
    def __init__(self):
        self.client = None
        self.proxies = []
        self.current_proxy_index = 0
        self.load_proxies()
        self.setup_client()
    
    def load_proxies(self):
        """Load proxies from proxies.txt"""
        try:
            proxy_file = os.path.join(os.path.dirname(__file__), 'proxies.txt')
            if os.path.exists(proxy_file):
                with open(proxy_file, 'r') as f:
                    # Filter out comments and empty lines
                    self.proxies = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                print(f"Loaded {len(self.proxies)} proxies.")
            else:
                print("proxies.txt not found. No proxies loaded.")
        except Exception as e:
            print(f"Error loading proxies: {str(e)}")

    def get_next_proxy(self) -> Optional[str]:
        """Get the next proxy from the list"""
        if not self.proxies:
            return None
        
        # Simple round-robin or random choice
        proxy = random.choice(self.proxies)
        print(f"Switching to proxy: {proxy}")
        return proxy

    def setup_client(self):
        """Initialize the Instagram client with proper settings"""
        self.client = Client()
        
        # Set realistic device settings to avoid detection
        self.client.set_settings({
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

    def apply_proxy(self):
        """Apply a proxy to the client if available"""
        proxy = self.get_next_proxy()
        if proxy:
            self.client.set_proxy(proxy)
            return True
        return False
    
    def authenticate_user(self, username: str, password: str, max_retries: int = 3) -> Tuple[bool, str, Optional[Client], Optional[Dict[str, Any]]]:
        """
        Authenticate user with Instagram servers.
        Retries with different proxies if connection/rate limit errors occur.
        
        Args:
            username: Instagram username
            password: Instagram password
            max_retries: Number of proxy retries
            
        Returns:
            Tuple of (success, message, client, user_info)
        """
        attempts = 0
        last_error = ""

        while attempts <= max_retries:
            try:
                # Apply proxy for this attempt (skips if no proxies)
                if self.proxies:
                   current_proxy = self.get_next_proxy()
                   if current_proxy:
                       print(f"Attempt {attempts+1}: Using proxy {current_proxy}")
                       self.client.set_proxy(current_proxy)
                else:
                    if attempts > 0:
                        print("No proxies available for retry. Stopping.")
                        break

                # Add realistic delay before login to simulate human behavior
                time.sleep(random.uniform(2, 5))
                
                # Attempt to login
                self.client.login(username, password)
                
                # If login successful, get user info
                user_info = self.client.user_info_by_username(username)
                
                return True, "Authentication successful", self.client, {
                    'user_id': user_info.pk,
                    'username': user_info.username,
                    'full_name': user_info.full_name,
                    'follower_count': user_info.follower_count,
                    'following_count': user_info.following_count,
                    'is_private': user_info.is_private,
                    'profile_pic_url': user_info.profile_pic_url
                }
                
            except TwoFactorRequired:
                return False, "2FA_REQUIRED", None, None
                
            except BadCredentials:
                return False, "INVALID_CREDENTIALS", None, None
                
            except ChallengeRequired:
                last_error = "CHALLENGE_REQUIRED"
                # Challenges often mean IP is flagged, so retry might help if we had more proxies
                # But typically requires browser intervention.
                # We'll treat as a soft fail to try another proxy if available.
                
            except (PleaseWaitFewMinutes, RateLimitError):
                last_error = "RATE_LIMITED"
                print(f"Rate limited on attempt {attempts+1}. Retrying with new proxy...")
                
            except Exception as e:
                error_msg = str(e).lower()
                last_error = f"AUTH_ERROR: {str(e)}"
                
                if 'suspicious' in error_msg or 'connection' in error_msg or 'timeout' in error_msg:
                    print(f"Connection/Suspicious error on attempt {attempts+1}: {error_msg}. Retrying...")
                else:
                    # Unknown error, might not be proxy related, but safe to retry once more
                    print(f"Unknown error on attempt {attempts+1}: {error_msg}")

            attempts += 1
            if attempts <= max_retries:
                 time.sleep(2) # Short pause before retry

        # If we exhausted retries
        return False, f"Failed after {attempts} attempts. Last error: {last_error}", None, None
    
    def authenticate_with_2fa(self, username: str, password: str, verification_code: str) -> Tuple[bool, str, Optional[Client], Optional[Dict[str, Any]]]:
        """
        Authenticate user with Instagram servers using 2FA code
        
        Args:
            username: Instagram username
            password: Instagram password
            verification_code: 2FA verification code
            
        Returns:
            Tuple of (success, message, client, user_info)
        """
        try:
            # We assume proxy is already set from the initial authenticate_user call 
            # or we can set it again if we want to be safe, but usually 2FA follows immediately
            # on the same session/IP to avoid suspicion.
            
            # Add realistic delay before login to simulate human behavior
            time.sleep(random.uniform(1, 3))
            
            # Attempt to login with 2FA code
            self.client.login(username, password, verification_code=verification_code)
            
            # If login successful, get user info
            user_info = self.client.user_info_by_username(username)
            
            return True, "2FA Authentication successful", self.client, {
                'user_id': user_info.pk,
                'username': user_info.username,
                'full_name': user_info.full_name,
                'follower_count': user_info.follower_count,
                'following_count': user_info.following_count,
                'is_private': user_info.is_private,
                'profile_pic_url': user_info.profile_pic_url
            }
            
        except BadCredentials:
            return False, "INVALID_CREDENTIALS_OR_CODE", None, None
            
        except Exception as e:
            return False, f"2FA_AUTH_ERROR: {str(e)}", None, None
    
    def test_connection(self, username: str, password: str) -> Dict[str, Any]:
        """
        Test the connection to Instagram servers
        
        Args:
            username: Instagram username
            password: Instagram password
            
        Returns:
            Dictionary with connection test results
        """
        result = {
            'connected': False,
            'message': '',
            'user_info': None,
            'requires_2fa': False
        }
        
        success, message, client, user_info = self.authenticate_user(username, password)
        
        result['connected'] = success
        result['message'] = message
        result['user_info'] = user_info
        result['requires_2fa'] = (message == "2FA_REQUIRED")
        
        return result


# Standalone function for easy use
def authenticate_instagram_user(username: str, password: str) -> Tuple[bool, str, Optional[Client], Optional[Dict[str, Any]]]:
    """
    Standalone function to authenticate Instagram user
    
    Args:
        username: Instagram username
        password: Instagram password
        
    Returns:
        Tuple of (success, message, client, user_info)
    """
    handler = InstagramAuthHandler()
    return handler.authenticate_user(username, password)


def authenticate_instagram_user_with_2fa(username: str, password: str, verification_code: str) -> Tuple[bool, str, Optional[Client], Optional[Dict[str, Any]]]:
    """
    Standalone function to authenticate Instagram user with 2FA
    
    Args:
        username: Instagram username
        password: Instagram password
        verification_code: 2FA verification code
        
    Returns:
        Tuple of (success, message, client, user_info)
    """
    handler = InstagramAuthHandler()
    return handler.authenticate_with_2fa(username, password, verification_code)


def test_instagram_connection(username: str, password: str) -> Dict[str, Any]:
    """
    Test connection to Instagram servers
    
    Args:
        username: Instagram username
        password: Instagram password
        
    Returns:
        Dictionary with connection test results
    """
    handler = InstagramAuthHandler()
    return handler.test_connection(username, password)


# For testing purposes
if __name__ == "__main__":
    print("Instagram Authentication Handler Test")
    print("="*40)
    
    username = input("Enter Instagram username: ")
    password = input("Enter Instagram password: ")
    
    print(f"\nTesting connection for @{username}...")
    
    result = test_instagram_connection(username, password)
    
    print(f"Connected: {result['connected']}")
    print(f"Message: {result['message']}")
    print(f"Requires 2FA: {result['requires_2fa']}")
    
    if result['user_info']:
        print(f"User Info: {result['user_info']['full_name']} (@{result['user_info']['username']})")
        print(f"Followers: {result['user_info']['follower_count']}")