import sqlite3
import os

db_path = os.path.join('instance', 'zenflow.db')

def migrate():
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    columns_to_add = [
        ("free_tokens", "INTEGER DEFAULT 4000"),
        ("paid_tokens", "INTEGER DEFAULT 0"),
        ("tokens_reset_at", "DATETIME")
    ]

    for col_name, col_type in columns_to_add:
        try:
            print(f"Adding column {col_name} to user table...")
            cursor.execute(f"ALTER TABLE user ADD COLUMN {col_name} {col_type}")
            print(f"Successfully added {col_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"Column {col_name} already exists.")
            else:
                print(f"Error adding {col_name}: {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
