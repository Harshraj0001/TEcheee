import sqlite3

DATABASE = "instance/iot.db"

connection = sqlite3.connect(DATABASE)
cursor = connection.cursor()

try:
    cursor.execute("""
        ALTER TABLE device
        ADD COLUMN api_key VARCHAR(100)
    """)

    connection.commit()

    print("api_key column added successfully!")

except sqlite3.OperationalError as error:
    print("Database update:", error)

finally:
    connection.close()