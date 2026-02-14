import sqlite3
import os

def migrate():
    db_path = 'instance/zenflow.db'
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Checking for is_admin column in user table...")
    cursor.execute("PRAGMA table_info(user)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'is_admin' not in columns:
        print("Adding is_admin column to user table...")
        cursor.execute("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0")
    else:
        print("is_admin column already exists.")

    print("Checking for activity_log table...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activity_log'")
    if not cursor.fetchone():
        print("Creating activity_log table...")
        cursor.execute('''
            CREATE TABLE activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action VARCHAR(100) NOT NULL,
                details TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES user (id)
            )
        ''')
    else:
        print("activity_log table already exists.")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
