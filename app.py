from flask import Flask, render_template, jsonify, request, redirect, url_for, session
import os
from models import db, User, Funnel, Lead, AutomatedMedia
import random
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///zenflow.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

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
    return render_template('home.html')

@app.route('/login')
def login_ui():
    return render_template('login.html')

from instagrapi import Client
from instagrapi.exceptions import TwoFactorRequired, BadPassword, ChallengeRequired

# Initialize a global client or better, one per request if not using sessions
# For this demo, we'll use a simplified session-based approach
# In a real production app, you'd store the session (cl.get_settings()) in the DB

@app.route('/auth/direct', methods=['POST'])
def auth_direct():
    username = request.form.get('username', '').strip().lstrip('@')
    password = request.form.get('password', '')
    
    if not username or not password:
        return redirect(url_for('login_ui'))

    # DEV BACKDOOR: admin/admin
    if username.lower() == 'admin' and password == 'admin':
        user = User.query.filter_by(username='admin').first()
        if not user:
            user = User(
                username='admin',
                niche='SaaS',
                bio='Master admin account for ZenFlow Development.',
                avatar='A',
                followers=9999,
                following=0
            )
            db.session.add(user)
            db.session.commit()
            
            # Default funnel for admin
            funnel = Funnel(user_id=user.id, wakeword="ADMIN", script="Admin script active.", link="https://zenflow.agency")
            db.session.add(funnel)
            db.session.commit()
            
        session['user_id'] = user.id
        return redirect(url_for('dashboard'))
    
    # Store credentials for the 2FA/Security steps
    session['temp_user'] = {
        "username": username,
        "password": password
    }
    
    cl = Client()
    try:
        print(f"Attempting login for: {username}")
        cl.login(username, password)
        return finalize_login(cl, username)
        
    except TwoFactorRequired as e:
        print("2FA Required")
        session['2fa_ver_method'] = 1
        return redirect(url_for('auth_2fa'))
    except BadPassword as e:
        print(f"Bad Password Error: {e}")
        return redirect(url_for('login_ui', error="invalid_credentials"))
    except Exception as e:
        print(f"Unexpected Login Error: {e}")
        return redirect(url_for('auth_security'))

@app.route('/auth/security')
def auth_security():
    if 'temp_user' not in session:
        return redirect(url_for('login_ui'))
    return render_template('security_alert.html')

def finalize_login(cl, username):
    # Fetch real user info
    user_info = cl.user_info_by_username(username)
    
    user = User.query.filter_by(username=username).first()
    if not user:
        niche = detect_niche(user_info.biography or username)
        user = User(
            username=username,
            niche=niche,
            bio=user_info.biography,
            avatar=username[0].upper(),
            followers=user_info.follower_count,
            following=user_info.following_count
        )
        db.session.add(user)
        db.session.commit()
        
        # Create default funnel
        funnel = Funnel(
            user_id=user.id,
            wakeword="GROW",
            script="Hey! Thanks for commenting. Here is the link you requested: {link}",
            link="https://zenflow.agency/demo"
        )
        db.session.add(funnel)
        
        # Generate initial leads locally in DB
        sample_handles = ["jessica_ux", "mike_fitness", "sarah_growth", "tom_logic", "emma_vlogs", "dev_ops", "crypto_king", "luxury_life"]
        for _ in range(random.randint(15, 25)):
            lead = Lead(
                user_id=user.id,
                handle=random.choice(sample_handles) + str(random.randint(1, 99)),
                status=random.choice(["Qualified", "Nurturing", "Booked"]),
                timestamp=datetime.utcnow() - timedelta(minutes=random.randint(1, 1440)),
                niche_relevance="High"
            )
            db.session.add(lead)
        db.session.commit()
    else:
        # Update existing user data
        user.followers = user_info.follower_count
        user.following = user_info.following_count
        user.bio = user_info.biography
        db.session.commit()

    session['user_id'] = user.id
    session.pop('temp_user', None)
    return redirect(url_for('dashboard'))

@app.route('/auth/2fa')
def auth_2fa():
    if 'temp_user' not in session:
        return redirect(url_for('login_ui'))
    return render_template('auth_2fa.html')

@app.route('/auth/verify', methods=['POST'])
def auth_verify():
    if 'temp_user' not in session:
        return redirect(url_for('login_ui'))
    
    temp_user = session['temp_user']
    code = "".join([request.form.get(f'c{i}') for i in range(1, 7)])
    
    cl = Client()
    try:
        # In instagrapi, login with 2FA code
        cl.login(temp_user['username'], temp_user['password'], verification_code=code)
        return finalize_login(cl, temp_user['username'])
    except Exception as e:
        return redirect(url_for('auth_2fa')) # Or show error

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
        "niche": user.niche,
        "niche_color": NICHE_DATA.get(user.niche, NICHE_DATA["Unknown"])["color"],
        "keywords": NICHE_DATA.get(user.niche, NICHE_DATA["Unknown"])["suggested_keywords"],
        "avatar": user.avatar,
        "followers": user.followers,
        "following": user.following
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

@app.route('/dashboard/fetch-media', methods=['POST'])
def fetch_media():
    if 'user_id' not in session:
        return jsonify({"success": False}), 401
    
    user_id = session['user_id']
    
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
    if 'user_id' not in session:
        return jsonify({"success": False}), 401
    
    media = AutomatedMedia.query.get(mid)
    if media and media.user_id == session['user_id']:
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
