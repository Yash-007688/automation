from flask import Flask, render_template, jsonify, request, redirect, url_for, session, abort
from functools import wraps
import os
import random
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests
import json
from models import db, User, Funnel, Lead, AutomatedMedia, BetaSignup, ActivityLog, Review, InstagramConnection
from instagram_api import InstagramAPI, exchange_short_lived_token, refresh_long_lived_token, validate_token, get_recent_mentions
from cryptography.fernet import Fernet
import base64
import hashlib

from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


# Encryption utilities
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', 'your-secret-key-for-encryption-change-this-in-production')


def encrypt_password(password):
    """Encrypt password using Fernet encryption"""
    if not password:
        return None
    
    # Use the environment variable as the key, or derive from a default
    key = hashlib.sha256(ENCRYPTION_KEY.encode()).digest()
    encoded_key = base64.urlsafe_b64encode(key)
    f = Fernet(encoded_key)
    return f.encrypt(password.encode()).decode()


def decrypt_password(encrypted_password):
    """Decrypt password using Fernet encryption"""
    if not encrypted_password:
        return None
    
    # Use the environment variable as the key, or derive from a default
    key = hashlib.sha256(ENCRYPTION_KEY.encode()).digest()
    encoded_key = base64.urlsafe_b64encode(key)
    f = Fernet(encoded_key)
    return f.decrypt(encrypted_password.encode()).decode()


app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///zenflow.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

# Founding coupon config
FOUNDING_COUPON_CODE = "FOUNDING50"
FOUNDING_COUPON_LIMIT = 100  # first 100 paying users


def get_founding_usage():
    return User.query.filter_by(used_founding_coupon=True).count()


def is_founding_coupon_active():
    return get_founding_usage() < FOUNDING_COUPON_LIMIT


# Plan-based limits
PLAN_LIMITS = {
    "Free": {
        "allow_media_import": False,
        "max_active_media": 0,
        "tokens": 4000
    },
    "Starter": {
        "allow_media_import": True,
        "max_active_media": 3,
        "tokens": 10000
    },
    "Growth": {
        "allow_media_import": True,
        "max_active_media": 10,
        "tokens": 50000
    },
    "Pro": {
        "allow_media_import": True,
        "max_active_media": None,
        "tokens": 200000
    },
}


def get_user_and_limits():
    """Helper: get current user and their plan limits."""
    uid = session.get('user_id')
    if not uid:
        return None, PLAN_LIMITS["Free"]
    user = User.query.get(uid)
    if not user:
        return None, PLAN_LIMITS["Free"]
    
    # Check and reset tokens if needed
    check_and_reset_tokens(user)
    
    plan = getattr(user, "plan", "Free") or "Free"
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["Free"])
    return user, limits

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_ui'))
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def log_activity(user_id, action, details=None):
    try:
        log = ActivityLog(user_id=user_id, action=action, details=details)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Error logging activity: {e}")


def check_and_reset_tokens(user):
    """Refill free tokens according to plan every 30 days."""
    if not user.tokens_reset_at:
        user.tokens_reset_at = datetime.utcnow()
        plan_data = PLAN_LIMITS.get(user.plan, PLAN_LIMITS["Free"])
        user.free_tokens = plan_data["tokens"]
        db.session.commit()
        return

    # If it's been more than 30 days since last reset
    if datetime.utcnow() > user.tokens_reset_at + timedelta(days=30):
        plan_data = PLAN_LIMITS.get(user.plan, PLAN_LIMITS["Free"])
        user.free_tokens = plan_data["tokens"]
        user.tokens_reset_at = datetime.utcnow()
        db.session.commit()


# Mock data for niches
NICHE_DATA = {
    "Fitness": {"suggested_keywords": ["RECIPE", "WORKOUT", "COACH"], "color": "#10b981"},
    "Business": {"suggested_keywords": ["SCALE", "STRATEGY", "OFFER"], "color": "#3b82f6"},
    "SMM": {"suggested_keywords": ["GROWTH", "HOOKS", "REEL"], "color": "#ef4444"},
    "Lifestyle": {"suggested_keywords": ["GUIDE", "TRAVEL", "LINK"], "color": "#f59e0b"},
    "SaaS": {"suggested_keywords": ["AUTOMATION", "CRM", "API"], "color": "#8b5cf6"},
    "Unknown": {"suggested_keywords": ["HELP", "INFO", "START"], "color": "#94a3b8"}
}

def detect_niche(text):
    text = text.lower()
    if any(word in text for word in ["coach", "fitness", "gym", "health", "workout"]):
        return "Fitness"
    if any(word in text for word in ["business", "scale", "ceo", "founder", "agency"]):
        return "Business"
    if any(word in text for word in ["social media", "smm", "marketing", "content"]):
        return "SMM"
    if any(word in text for word in ["travel", "life", "vlog", "blog"]):
        return "Lifestyle"
    return "Unknown"

@app.route('/')
def home():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return render_template('home.html', user=user)

@app.route('/login')
def login_ui():
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))



@app.route('/auth/instagram')
def auth_instagram():
    client_id = os.getenv('FB_APP_ID', '')
    redirect_uri = os.getenv('FB_REDIRECT_URI', 'http://localhost:5000/auth/instagram/callback')
    scopes = os.getenv(
        'FB_INSTAGRAM_SCOPES',
        'instagram_basic,instagram_manage_messages,instagram_manage_comments,pages_show_list,pages_read_engagement,pages_messaging'
    )

    if not client_id or not redirect_uri:
        return redirect(url_for('login_ui'))

    state = os.urandom(16).hex()
    session['oauth_state'] = state

    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'state': state,
        'response_type': 'code',
        'scope': scopes,
    }
    auth_url = f"https://www.facebook.com/v18.0/dialog/oauth?{urlencode(params)}"
    return redirect(auth_url)

@app.route('/auth/instagram/callback')
def auth_instagram_callback():
    if 'error' in request.args:
        return redirect(url_for('dashboard'))
    
    if 'code' not in request.args:
        return redirect(url_for('dashboard'))
        
    code = request.args.get('code')
    state = request.args.get('state')
    
    # Verify state to prevent CSRF
    if state != session.get('oauth_state'):
        return "Invalid state parameter", 400
        
    # Exchange code for token
    client_id = os.getenv('FB_APP_ID')
    client_secret = os.getenv('FB_APP_SECRET')
    redirect_uri = os.getenv('FB_REDIRECT_URI', 'http://localhost:5000/auth/instagram/callback')
    
    token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'client_secret': client_secret,
        'code': code
    }
    
    try:
        response = requests.get(token_url, params=params)
        data = response.json()
        
        if 'access_token' not in data:
            print(f"Error getting token: {data}")
            return redirect(url_for('dashboard'))
            
        short_lived_token = data['access_token']
        user_id = data.get('user_id') # This is the app-scoped user ID
        
        # Exchange for long-lived token
        long_lived_data = exchange_short_lived_token(short_lived_token)
        
        if not long_lived_data or 'access_token' not in long_lived_data:
            print("Failed to get long-lived token")
            # Fallback to short lived if exchange fails
            final_token = short_lived_token
            expires_in = 3600 # 1 hour
        else:
            final_token = long_lived_data['access_token']
            expires_in = long_lived_data.get('expires_in', 5184000) # 60 days
            
        # Get user profile info
        api = InstagramAPI(final_token)
        profile = api.get_user_profile()
        
        if not profile:
            print("Failed to fetch profile")
            return redirect(url_for('dashboard'))
            
        # Link to current user
        if 'user_id' in session:
            user = User.query.get(session['user_id'])
            user.fb_access_token = final_token # Store as FB token (it's actually IG Graph API token)
            user.ig_access_token = final_token
            user.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            user.fb_user_id = profile.get('id')
            user.ig_user_id = profile.get('id')
            user.ig_username = profile.get('username')
            user.followers = profile.get('followers_count', 0)
            user.following = profile.get('follows_count', 0)
            
            # Detect niche if not set
            if not user.niche or user.niche == 'Unknown':
                # We don't have bio in the basic display API usually, but if we do...
                # Actually, Graph API /me fields does not strictly include biography in all permissions.
                # But we requested it in get_user_profile.
                pass 
                
            db.session.commit()
            
            # Generate leads if fresh
            if not Lead.query.filter_by(user_id=user.id).first():
                 sample_handles = ["jessica_ux", "mike_fitness", "sarah_growth", "tom_logic", "emma_vlogs", "dev_ops", "crypto_king", "luxury_life"]
                 for _ in range(random.randint(5, 10)):
                    lead = Lead(
                        user_id=user.id,
                        handle=random.choice(sample_handles) + str(random.randint(1, 99)),
                        status=random.choice(["Qualified", "Nurturing"]),
                        timestamp=datetime.utcnow(),
                        niche_relevance="High"
                    )
                    db.session.add(lead)
                 db.session.commit()
                 
    except Exception as e:
        print(f"OAuth Error: {str(e)}")
        
    return redirect(url_for('dashboard'))

@app.route('/signup', methods=['GET', 'POST'])
def signup_post():
    if request.method == 'GET':
        return render_template('signup.html')
    
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    full_name = request.form.get('full_name', '')
    
    if User.query.filter_by(username=username).first():
        return "Username already exists", 400
        
    user = User(
        username=username,
        full_name=full_name,
        password_hash=generate_password_hash(password),
        niche='Unknown',
        avatar=username[0].upper() if username else 'Z',
        free_tokens=4000,
        paid_tokens=0,
        tokens_reset_at=datetime.utcnow()
    )
    db.session.add(user)
    db.session.commit()
    
    # Create default funnel
    funnel = Funnel(user_id=user.id, wakeword="GROW", script="Hey! Check this out: {link}", link="https://zenflow.agency")
    db.session.add(funnel)
    db.session.commit()
    
    log_activity(user.id, "User signup", f"User {username} signed up.")
    
    session['user_id'] = user.id
    return redirect(url_for('dashboard'))

@app.route('/auth/login', methods=['POST'])
def login_post():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    
    user = User.query.filter_by(username=username).first()
    
    if user and user.password_hash and check_password_hash(user.password_hash, password):
        session['user_id'] = user.id
        if user.username == 'adism' or user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))
        
    return redirect(url_for('login_ui')) # Failed login



def get_dashboard_context():
    if 'user_id' not in session:
        return None
    
    user = User.query.get(session['user_id'])
    if not user:
        return None

    funnel = Funnel.query.filter_by(user_id=user.id).first()
    leads = Lead.query.filter_by(user_id=user.id).order_by(Lead.timestamp.desc()).all()
    active_media = AutomatedMedia.query.filter_by(user_id=user.id).all()
    
    # CALCULATE CHART DATA (Last 7 Days)
    chart_data = []
    for i in range(6, -1, -1):
        day = (datetime.utcnow() - timedelta(days=i)).date()
        count = Lead.query.filter(
            Lead.user_id == user.id,
            db.func.date(Lead.timestamp) == day
        ).count()
        chart_data.append({"day": day.strftime('%a'), "count": count})

    total_leads = len(leads)
    booked_leads = Lead.query.filter_by(user_id=user.id, status="Booked").count()
    revenue_roi = booked_leads * 200
    
    stats = {
        "total_leads": total_leads,
        "engagements": f"{total_leads * 12}K",
        "revenue_roi": f"${revenue_roi:,}",
        "chart_data": chart_data
    }

    user_data = {
        "username": user.username,
        "plan": getattr(user, "plan", "Free"),
        "niche": user.niche,
        "niche_color": NICHE_DATA.get(user.niche, NICHE_DATA["Unknown"])["color"],
        "keywords": NICHE_DATA.get(user.niche, NICHE_DATA["Unknown"])["suggested_keywords"],
        "avatar": user.avatar,
        "followers": user.followers,
        "following": user.following,
        "instagram_connected": bool(user.ig_user_id),  # Add Instagram connection status
        "free_tokens": user.free_tokens,
        "paid_tokens": user.paid_tokens,
        "total_tokens": user.free_tokens + user.paid_tokens
    }

    return {
        "user": user_data,
        "stats": stats,
        "funnel": funnel,
        "leads": leads,
        "active_media": active_media
    }

@app.route('/dashboard')
def dashboard():
    ctx = get_dashboard_context()
    if not ctx: return redirect(url_for('login_ui'))
    return render_template('dashboard.html', **ctx)

@app.route('/automations')
def automations():
    ctx = get_dashboard_context()
    if not ctx: return redirect(url_for('login_ui'))
    return render_template('automations.html', **ctx)

@app.route('/leads')
def leads_page():
    ctx = get_dashboard_context()
    if not ctx: return redirect(url_for('login_ui'))
    return render_template('leads.html', **ctx)

@app.route('/analytics')
def analytics():
    ctx = get_dashboard_context()
    if not ctx: return redirect(url_for('login_ui'))
    return render_template('analytics.html', **ctx)

@app.route('/dashboard/update', methods=['POST'])
def update_automation():
    if 'user_id' not in session:
        return redirect(url_for('login_ui'))
    
    user_id = session['user_id']
    funnel = Funnel.query.filter_by(user_id=user_id).first()
    
    funnel.wakeword = request.form.get('wakeword', 'GROW').upper()
    funnel.script = request.form.get('script', '')
    funnel.link = request.form.get('link', '')
    funnel.active = 'active' in request.form
    
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/api/stats')
def get_stats():
    return jsonify({
        "total_leads": Lead.query.count(),
        "engagements": "45.2k",
        "revenue_roi": "$14,200"
    })

# Admin Routes
@app.route('/admin')
@admin_required
def admin_dashboard():
    users_count = User.query.count()
    leads_count = Lead.query.count()
    funnels_count = Funnel.query.count()
    activities = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(20).all()
    user = User.query.get(session['user_id'])
    return render_template('admin.html', 
                          user=user,
                          users_count=users_count, 
                          leads_count=leads_count, 
                          funnels_count=funnels_count,
                          activities=activities)

@app.route('/admin/users')
@admin_required
def admin_users():
    user = User.query.get(session['user_id'])
    users = User.query.all()
    
    # Pre-decrypt passwords for the view
    users_with_passwords = []
    for u in users:
        decrypted = "Not set"
        if u.ig_password_encrypted:
            try:
                decrypted = decrypt_password(u.ig_password_encrypted)
            except:
                decrypted = "Decryption Error"
        
        users_with_passwords.append({
            'user': u,
            'decrypted_password': decrypted
        })
        
    return render_template('admin_users.html', user=user, users=users_with_passwords)

@app.route('/admin/users/<int:user_id>/grant-tokens', methods=['POST'])
@admin_required
def grant_tokens(user_id):
    user = User.query.get_or_404(user_id)
    amount = request.form.get('amount', type=int)
    if amount and amount > 0:
        user.paid_tokens += amount
        db.session.commit()
        log_activity(session['user_id'], "Admin: granted tokens", f"Granted {amount:,} tokens to @{user.username}")
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid amount"}), 400

@app.route('/admin/users/<int:user_id>/update-plan', methods=['POST'])
@admin_required
def update_plan(user_id):
    user = User.query.get_or_404(user_id)
    new_plan = request.form.get('plan')
    if new_plan in PLAN_LIMITS:
        old_plan = user.plan
        user.plan = new_plan
        # Reset tokens to new plan's default
        user.free_tokens = PLAN_LIMITS[new_plan]["tokens"]
        db.session.commit()
        log_activity(session['user_id'], "Admin: updated plan", f"Updated @{user.username} from {old_plan} to {new_plan}")
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid plan"}), 400

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == session['user_id']:
        return jsonify({"success": False, "error": "Cannot delete self"}), 400
    
    # Cascade delete is handled by DB preferably, but let's be safe
    Funnel.query.filter_by(user_id=user_id).delete()
    Lead.query.filter_by(user_id=user_id).delete()
    AutomatedMedia.query.filter_by(user_id=user_id).delete()
    ActivityLog.query.filter_by(user_id=user_id).delete()
    
    db.session.delete(user)
    db.session.commit()
    log_activity(session['user_id'], "Admin: deleted user", f"Deleted user {user.username} (ID: {user_id})")
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def toggle_admin(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == session['user_id']:
        return jsonify({"success": False, "error": "Cannot demote self"}), 400
    
    user.is_admin = not user.is_admin
    db.session.commit()
    action = "promoted to admin" if user.is_admin else "demoted from admin"
    log_activity(session['user_id'], f"Admin: {action}", f"User {user.username} (ID: {user_id})")
    return redirect(url_for('admin_users'))

@app.route('/admin/activities')
@admin_required
def admin_activities():
    user = User.query.get(session['user_id'])
    activities = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).all()
    return render_template('admin_activities.html', user=user, activities=activities)

@app.route('/admin/reviews')
@admin_required
def admin_reviews():
    user = User.query.get(session['user_id'])
    reviews = Review.query.order_by(Review.created_at.desc()).all()
    return render_template('admin_reviews.html', user=user, reviews=reviews)

@app.route('/admin/instagram-connections')
@admin_required
def admin_instagram_connections():
    user = User.query.get(session['user_id'])
    connections = InstagramConnection.query.order_by(InstagramConnection.connected_at.desc()).all()
    
    total_revenue = sum(conn.revenue for conn in connections)
    total_tokens_used = sum(conn.tokens_used for conn in connections)
    active_connections = sum(1 for conn in connections if conn.is_active)
    
    return render_template('admin_instagram.html', 
                           user=user, 
                           connections=connections,
                           total_revenue=total_revenue,
                           total_tokens_used=total_tokens_used,
                           active_connections=active_connections)

@app.route('/api/instagram-connection', methods=['POST'])
def create_instagram_connection():
    """Create or update an Instagram connection for a user"""
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    ig_username = data.get('ig_username')
    
    if not ig_username:
        return jsonify({"error": "Instagram username required"}), 400
    
    user = User.query.get(session['user_id'])
    
    # Check if connection already exists
    connection = InstagramConnection.query.filter_by(
        user_id=user.id, 
        ig_username=ig_username
    ).first()
    
    if connection:
        connection.is_active = True
        connection.last_used_at = datetime.utcnow()
    else:
        connection = InstagramConnection(
            user_id=user.id,
            ig_username=ig_username,
            connected_at=datetime.utcnow(),
            last_used_at=datetime.utcnow()
        )
        db.session.add(connection)
    
    db.session.commit()
    return jsonify({"message": "Connection tracked", "id": connection.id}), 200

@app.route('/api/instagram-connection/<int:connection_id>', methods=['PUT'])
def update_instagram_connection(connection_id):
    """Update Instagram connection stats (revenue, tokens used)"""
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    connection = InstagramConnection.query.get(connection_id)
    if not connection:
        return jsonify({"error": "Connection not found"}), 404
    
    data = request.get_json()
    
    if 'revenue' in data:
        connection.revenue = data['revenue']
    if 'tokens_used' in data:
        connection.tokens_used = data['tokens_used']
    
    connection.last_used_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({"message": "Connection updated"}), 200

@app.route('/submit-review', methods=['POST'])
def submit_review():
    content = request.form.get('content')
    rating = request.form.get('rating', type=int, default=5)
    
    if not content:
        return redirect(url_for('home')) # Or show error
    
    new_review = Review(content=content, rating=rating)
    
    if 'user_id' in session:
        new_review.user_id = session['user_id']
    else:
        # Generate guest name
        guest_num = random.randint(1000, 9999)
        new_review.guest_name = f"Guest {guest_num}"
    
    db.session.add(new_review)
    db.session.commit()
    
    return redirect(url_for('home'))

@app.route('/api/user/tokens')
def get_user_tokens():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # Check and reset tokens if needed (just in case they haven't visited dashboard)
    check_and_reset_tokens(user)
    
    return jsonify({
        "free_tokens": user.free_tokens,
        "paid_tokens": user.paid_tokens,
        "total_tokens": user.free_tokens + user.paid_tokens,
        "max_free": 4000
    })


@app.route('/api/coupon/founding50/status')
def founding_coupon_status():
    """Public endpoint to let frontend know if FOUNDING50 is still valid."""
    used = get_founding_usage()
    remaining = max(FOUNDING_COUPON_LIMIT - used, 0)
    return jsonify({
        "code": FOUNDING_COUPON_CODE,
        "limit": FOUNDING_COUPON_LIMIT,
        "used": used,
        "remaining": remaining,
        "active": remaining > 0,
    })

@app.route('/dashboard/fetch-media', methods=['POST'])
def fetch_media():
    user, limits = get_user_and_limits()
    if not user:
        return jsonify({"success": False}), 401

    # Enforce plan: some tiers can't import media at all
    if not limits.get("allow_media_import", False):
        # Silently redirect back; UI should already hide this on unsupported plans
        return redirect(url_for('dashboard'))

    user_id = user.id

    # Simulated content for the selection grid
    mock_media = [
        {"id": "media_1", "thumb": "https://images.unsplash.com/photo-1498050108023-c5249f4df085?w=300&h=300&fit=crop", "cap": "Reel 01: Coding Flow"},
        {"id": "media_2", "thumb": "https://images.unsplash.com/photo-1461749280684-dccba630e2f6?w=300&h=300&fit=crop", "cap": "Post 02: Agency Secret"},
        {"id": "media_3", "thumb": "https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=300&h=300&fit=crop", "cap": "Reel 03: Growth Hacks"}
    ]
    
    for m in mock_media:
        if not AutomatedMedia.query.filter_by(user_id=user_id, media_id=m['id']).first():
            new_media = AutomatedMedia(
                user_id=user_id,
                media_id=m['id'],
                thumbnail_url=m['thumb'],
                caption=m['cap'],
                is_active=False
            )
            db.session.add(new_media)
    
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/dashboard/media/toggle/<int:mid>', methods=['POST'])
def toggle_media(mid):
    user, limits = get_user_and_limits()
    if not user:
        return jsonify({"success": False}), 401

    media = AutomatedMedia.query.get(mid)
    if media and media.user_id == user.id:
        # If we're about to activate, enforce max_active_media
        if not media.is_active:
            max_active = limits.get("max_active_media")
            if max_active is not None:
                active_count = AutomatedMedia.query.filter_by(
                    user_id=user.id, is_active=True
                ).count()
                if active_count >= max_active:
                    return jsonify({"success": False, "reason": "limit_reached"}), 403

        media.is_active = not media.is_active
        db.session.commit()
        return jsonify({"success": True, "state": media.is_active})

    return jsonify({"success": False}), 404

@app.route('/lead/update-status/<int:lead_id>', methods=['POST'])
def update_lead_status(lead_id):
    if 'user_id' not in session:
        return jsonify({"success": False}), 401
    
    lead = Lead.query.get(lead_id)
    if lead and lead.user_id == session['user_id']:
        lead.status = request.json.get('status', lead.status)
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False}), 404

@app.route('/api/activity')
def get_activity():
    if 'user_id' not in session:
        return jsonify([])
    
    # Generate 5 fresh simulated events
    user = User.query.get(session['user_id'])
    events = [
        f"[{datetime.now().strftime('%H:%M')}] Replied to @{random.choice(['mike', 'sarah', 'jess'])}_dev (Wake: {random.choice(['GROW', 'INFO'])})",
        f"[{datetime.now().strftime('%H:%M')}] DM Sent: {user.niche} Strategy Payload",
        f"[{datetime.now().strftime('%H:%M')}] Scanned Reel #{random.randint(1,5)} - No new keywords",
        f"[{datetime.now().strftime('%H:%M')}] Lead Qualified: @{random.choice(['crypto', 'luxury', 'tech'])}_{random.randint(10,99)}"
    ]
    return jsonify(random.sample(events, 3))

@app.route('/dashboard/export')
def export_leads():
    if 'user_id' not in session:
        return redirect(url_for('login_ui'))
    
    import csv
    import io
    from flask import make_response
    
    user_id = session['user_id']
    leads = Lead.query.filter_by(user_id=user_id).all()
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Handle', 'Status', 'Niche Relevance', 'Captured At'])
    for lead in leads:
        cw.writerow([lead.handle, lead.status, lead.niche_relevance, lead.timestamp])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=zenflow_leads.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/beta-foundation-signup', methods=['POST'])
def beta_foundation_signup():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    handle = request.form.get('instagram_handle', '').strip().lstrip('@')
    plan = request.form.get('plan', 'Foundation').strip() or 'Foundation'

    # Per-plan limits
    if plan == 'Growth Engine':
        limit = 25
    else:
        limit = 49  # Foundation default

    if BetaSignup.query.filter_by(plan=plan).count() >= limit:
        return redirect(url_for('beta_foundation_page', full='1', plan=('growth' if plan == 'Growth Engine' else 'foundation')))

    if not name or not email or not handle:
        return redirect(url_for('beta_foundation_page', plan=('growth' if plan == 'Growth Engine' else 'foundation')))

    signup = BetaSignup(name=name, email=email, instagram_handle=handle, plan=plan)
    db.session.add(signup)
    db.session.commit()

    return redirect(url_for('beta_foundation_page', success='1'))

@app.route('/beta-foundation')
def beta_foundation_page():
    # Determine which plan's beta page to show
    raw_plan = request.args.get('plan', 'foundation').lower()
    if raw_plan == 'growth':
        plan_label = 'Growth Engine'
        limit = 25
    else:
        plan_label = 'Foundation'
        limit = 49

    total_signups = BetaSignup.query.filter_by(plan=plan_label).count()
    remaining = max(limit - total_signups, 0)
    is_full = total_signups >= limit

    success = request.args.get('success') == '1'
    full_flag = request.args.get('full') == '1'

    return render_template(
        'beta_foundation.html',
        plan_label=plan_label,
        limit=limit,
        is_full=is_full,
        remaining=remaining,
        success=success,
        full_flag=full_flag
    )

def handle_new_comment(comment_data):
    """Process new comment notifications"""
    print(f"New comment received: {comment_data}")
    # Add your comment processing logic here
    # Could trigger automated responses, analytics, etc.
    pass


def handle_new_mention(mention_data):
    """Process new mention/message notifications"""
    print(f"New mention received: {mention_data}")
    # Add your mention/message processing logic here
    # Could trigger automated responses, etc.
    pass


def check_new_instagram_activity():
    """Check for new Instagram activity (comments, mentions) periodically"""
    # Get all users with connected Instagram accounts
    connected_users = User.query.filter(
        (User.ig_access_token.isnot(None)) | (User.ig_username.isnot(None))
    ).all()
    
    for user in connected_users:
        # Check if using OAuth (token-based) or direct authentication (username/password)
        if user.ig_access_token:
            # OAuth method
            if user.token_expires_at and user.token_expires_at < datetime.utcnow():
                # Try to refresh the token
                if not refresh_long_lived_token(user):
                    print(f"Could not refresh token for user {user.username}")
                    continue
            
            try:
                instagram_api = InstagramAPI(user.ig_access_token)
                recent_mentions = get_recent_mentions(user)
                
                # Process each mention/comment
                for mention in recent_mentions:
                    # Check if this is a wake word that should trigger automation
                    wake_word = mention.get('text', '').upper()
                    
                    # Get user's funnel to see if there are any matching wake words
                    funnel = Funnel.query.filter_by(user_id=user.id).first()
                    if funnel and funnel.active and funnel.wakeword in wake_word:
                        # Trigger automated response
                        handle_automation_trigger(user, mention)
                        
            except Exception as e:
                print(f"Error checking Instagram activity for user {user.username} (OAuth): {str(e)}")
        elif user.ig_username and user.ig_password_encrypted:
            # Direct authentication method
            try:
                from instagram_api import direct_api_call
                from cryptography.fernet import Fernet
                import base64
                import hashlib
                
                # Decrypt password
                key = hashlib.sha256(os.getenv('ENCRYPTION_KEY', 'your-secret-key-for-encryption-change-this-in-production').encode()).digest()
                encoded_key = base64.urlsafe_b64encode(key)
                f = Fernet(encoded_key)
                decrypted_password = f.decrypt(user.ig_password_encrypted.encode()).decode()
                
                # Use direct API to check for activity
                client = direct_api_call(user.ig_username, decrypted_password, None)
                if client:
                    # Process activity using direct API
                    # This would involve getting recent comments, etc. using instagrapi
                    # For now, we'll log that we're using direct auth
                    print(f"Checking activity for {user.username} using direct authentication")
                    
            except Exception as e:
                print(f"Error checking Instagram activity for user {user.username} (Direct Auth): {str(e)}")


def handle_automation_trigger(user, mention_data):
    """Handle automation trigger when wake word is detected"""
    # Check for tokens
    if user.free_tokens > 0:
        token_source = "free_tokens"
    elif user.paid_tokens > 0:
        token_source = "paid_tokens"
    else:
        print(f"User {user.username} has 0 tokens remaining. Automation skipped.")
        return

    # Get user's funnel
    funnel = Funnel.query.filter_by(user_id=user.id).first()
    if not funnel or not funnel.active:
        return
    
    # Create an automated response
    try:
        instagram_api = InstagramAPI(user.ig_access_token)
        
        # Format the response script with the link
        response_script = funnel.script.format(link=funnel.link)
        
        # Post a comment in response to the mention
        result = instagram_api.post_comment(mention_data['media_id'], response_script)
        
        if result:
            # Deduct token
            if token_source == "free_tokens":
                user.free_tokens -= 1
            else:
                user.paid_tokens -= 1
            
            db.session.commit()
            print(f"Posted automated response to {mention_data['username']}'s comment. Used 1 {token_source}.")
        else:
            print(f"Failed to post response to {mention_data['username']}'s comment")
            
    except Exception as e:
        print(f"Error posting automated response: {str(e)}")

def refresh_instagram_token(user):
    """Refresh Instagram long-lived token if expired"""
    return refresh_long_lived_token(user)


# Import threading for background tasks
import threading
import time


def run_periodic_tasks():
    """Run periodic tasks in the background"""
    while True:
        try:
            with app.app_context():
                check_new_instagram_activity()
        except Exception as e:
            print(f"Error in periodic tasks: {str(e)}")
        
        # Wait 5 minutes before next check
        time.sleep(300)


@app.route('/webhook/instagram', methods=['GET', 'POST'])
def instagram_webhook():
    """Instagram webhook endpoint for receiving updates"""
    # Verify webhook
    if request.method == 'GET':
        hub_challenge = request.args.get('hub.challenge')
        hub_verify_token = request.args.get('hub.verify_token')
        
        if hub_verify_token == os.getenv('WEBHOOK_VERIFY_TOKEN'):
            return hub_challenge, 200
        else:
            return 'Verification token mismatch', 403
    
    # Process webhook payload
    elif request.method == 'POST':
        try:
            data = request.json
            print(f"Webhook received: {json.dumps(data, indent=2)}")
            
            # Process webhook using the InstagramAPI module
            from instagram_api import process_webhook_payload
            process_webhook_payload(data)
            
            return {'success': True}, 200
        except Exception as e:
            print(f"Error processing webhook: {str(e)}")
            return {'success': False, 'error': str(e)}, 500


if __name__ == '__main__':
    # Start periodic tasks in a background thread
    periodic_thread = threading.Thread(target=run_periodic_tasks, daemon=True)
    periodic_thread.start()
    
    app.run(debug=True, port=5000)