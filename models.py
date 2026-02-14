from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(256))
    full_name = db.Column(db.String(100))
    fb_user_id = db.Column(db.String(120), unique=True)
    ig_user_id = db.Column(db.String(120), unique=True)
    fb_access_token = db.Column(db.Text)
    ig_access_token = db.Column(db.Text)
    token_expires_at = db.Column(db.DateTime)
    ig_username = db.Column(db.String(100))  # Store Instagram username separately
    ig_password_encrypted = db.Column(db.Text)  # Encrypted password
    ig_session_data = db.Column(db.Text)  # Store session data for direct API
    plan = db.Column(db.String(50), default="Free")
    used_founding_coupon = db.Column(db.Boolean, default=False)
    niche = db.Column(db.String(50))
    bio = db.Column(db.Text)
    avatar = db.Column(db.String(10))
    followers = db.Column(db.Integer, default=0)
    following = db.Column(db.Integer, default=0)
    
    # Token system
    free_tokens = db.Column(db.Integer, default=4000)
    paid_tokens = db.Column(db.Integer, default=0)
    tokens_reset_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    
    funnels = db.relationship('Funnel', backref='owner', lazy=True)
    leads = db.relationship('Lead', backref='owner', lazy=True)

class Funnel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    wakeword = db.Column(db.String(50), default="GROW")
    script = db.Column(db.Text)
    link = db.Column(db.String(200))
    active = db.Column(db.Boolean, default=True)

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    handle = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(50), default="Qualified")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    niche_relevance = db.Column(db.String(50))

class AutomatedMedia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    media_id = db.Column(db.String(100), nullable=False)
    thumbnail_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    caption = db.Column(db.Text)

class BetaSignup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    instagram_handle = db.Column(db.String(120), nullable=False)
    plan = db.Column(db.String(50), default="Foundation")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('activities', lazy=True))

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    guest_name = db.Column(db.String(100))
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, default=5)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('reviews', lazy=True))