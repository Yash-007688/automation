import sqlite3
import os

def promote_to_admin(username):
    db_path = 'instance/zenflow.db'
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("UPDATE user SET is_admin = 1 WHERE username = ?", (username,))
    if cursor.rowcount > 0:
        print(f"User {username} is now an admin.")
    else:
        print(f"User {username} not found.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    promote_to_admin('adism')
