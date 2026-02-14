#!/usr/bin/env python3
"""
Test script to diagnose and fix Instagram authentication issues
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from instagram_api import test_instagram_connection

def main():
    print("=" * 60)
    print("INSTAGRAM AUTHENTICATION TEST")
    print("=" * 60)
    
    print("\nThis test will help diagnose Instagram login issues.")
    print("Please enter your Instagram credentials for testing.\n")
    
    # Get credentials from user
    username = input("Enter Instagram username: ").strip()
    password = input("Enter Instagram password: ")
    
    if not username or not password:
        print("\nERROR: Both username and password are required!")
        return
    
    print(f"\nTesting connection for account: @{username}")
    print("This may take a moment...\n")
    
    # Test the connection
    client, user_info = test_instagram_connection(username, password)
    
    if client and user_info:
        print("\n✅ SUCCESS: Instagram connection established!")
        print(f"   Account: @{user_info.username}")
        print(f"   Full name: {user_info.full_name}")
        print(f"   Followers: {user_info.follower_count}")
        print(f"   Following: {user_info.following_count}")
        print(f"   Private: {'Yes' if user_info.is_private else 'No'}")
        print("\nThe authentication system is working correctly.")
    else:
        print("\n❌ FAILED: Could not establish Instagram connection")
        print("\nPossible solutions:")
        print("1. Check your username and password")
        print("2. Try logging into Instagram manually first to verify your account")
        print("3. Wait 24 hours if you've had multiple failed attempts (rate limit)")
        print("4. Use a different IP address or VPN if IP is blocked")
        print("5. Make sure your account isn't flagged for suspicious activity")
        print("6. Ensure your account is not a new account that requires verification")

if __name__ == "__main__":
    main()