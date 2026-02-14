from app import app, db, User, generate_password_hash

with app.app_context():
    user = User.query.filter_by(username='adism').first()
    if user:
        user.password_hash = generate_password_hash('admism')
        db.session.commit()
        print("Updated adism password to 'admism'")
    else:
        print("User adism not found")
