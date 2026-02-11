from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    niche = db.Column(db.String(50))
    bio = db.Column(db.Text)
    avatar = db.Column(db.String(10))
    followers = db.Column(db.Integer, default=0)
    following = db.Column(db.Integer, default=0)
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
