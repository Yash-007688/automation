#!/usr/bin/env python3
"""
Script to display all users in the database
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import User
from datetime import datetime

def display_users():
    print("=" * 80)
    print("USER DATABASE ENTRIES")
    print("=" * 80)
    
    with app.app_context():
        users = User.query.all()
        
        if not users:
            print("No users found in the database.")
            return
        
        print(f"\nTotal users: {len(users)}\n")
        
        for i, user in enumerate(users, 1):
            print(f"--- User #{i} ---")
            print(f"ID: {user.id}")
            print(f"Username: {user.username}")
            print(f"Instagram Username: {user.ig_username or 'Not set'}")
            print(f"Plan: {getattr(user, 'plan', 'Free')}")
            print(f"Email: {getattr(user, 'email', 'Not set')}")
            print(f"Full Name: {getattr(user, 'full_name', 'Not set')}")
            print(f"Bio: {user.bio or 'Not set'}")
            print(f"Avatar: {user.avatar}")
            print(f"Followers: {user.followers}")
            print(f"Following: {user.following}")
            print(f"Niche: {user.niche}")
            print(f"Free Tokens: {getattr(user, 'free_tokens', 'Not available')}")
            print(f"Paid Tokens: {getattr(user, 'paid_tokens', 'Not available')}")
            print(f"Tokens Reset At: {getattr(user, 'tokens_reset_at', 'Not set')}")
            print(f"Facebook User ID: {user.fb_user_id or 'Not set'}")
            print(f"Instagram User ID: {user.ig_user_id or 'Not set'}")
            print(f"Token Expires At: {user.token_expires_at or 'Not set'}")
            print(f"Used Founding Coupon: {getattr(user, 'used_founding_coupon', 'Not available')}")
            print(f"Created At: {getattr(user, 'created_at', 'Not set') if hasattr(user, 'created_at') else 'Not set'}")
            print("-" * 40)
            print()

if __name__ == "__main__":
    display_users()