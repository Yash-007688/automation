#!/usr/bin/env python3
"""
Script to create a new user with premium plan
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import User
from datetime import datetime
from werkzeug.security import generate_password_hash

def create_premium_user():
    username = "adism"
    password = "adism"
    full_name = "Adism User"
    
    print("=" * 50)
    print("CREATING NEW PREMIUM USER")
    print("=" * 50)
    
    with app.app_context():
        # Check if user already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"User '{username}' already exists!")
            print("Updating to premium plan...")
            existing_user.plan = "Pro"  # Premium plan
            existing_user.free_tokens = 4000
            existing_user.paid_tokens = 10000  # Bonus premium tokens
            existing_user.tokens_reset_at = datetime.utcnow()
            db.session.commit()
            print(f"User '{username}' updated to Pro plan with premium benefits!")
            return
        
        # Create new user with premium plan
        user = User(
            username=username,
            full_name=full_name,
            password_hash=generate_password_hash(password),
            niche='SaaS',
            bio='Premium user account',
            avatar=username[0].upper(),
            followers=0,
            following=0,
            plan="Pro",  # Premium plan
            free_tokens=4000,
            paid_tokens=10000,  # Bonus premium tokens
            tokens_reset_at=datetime.utcnow()
        )
        
        db.session.add(user)
        db.session.commit()
        
        print(f"✅ Successfully created user:")
        print(f"   Username: {user.username}")
        print(f"   Full Name: {user.full_name}")
        print(f"   Plan: {user.plan}")
        print(f"   Free Tokens: {user.free_tokens}")
        print(f"   Paid Tokens: {user.paid_tokens}")
        print(f"   Total Tokens: {user.free_tokens + user.paid_tokens}")
        print(f"   Password: {password} (for login)")

if __name__ == "__main__":
    create_premium_user()