from app import app, db, Review
with app.app_context():
    db.create_all()
    print("Tables in database:", db.engine.table_names())
    print("Review model check:", Review.query.all())
