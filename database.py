
import sqlite3

# Connect to existing database
conn = sqlite3.connect("appointments.db")
cursor = conn.cursor()

try:
    # Delete old appointment records first
    cursor.execute("DELETE FROM appointments")

    # Delete old student records
    cursor.execute("DELETE FROM students")

    # Delete old mentor records
    cursor.execute("DELETE FROM mentors")

    # Reset auto-increment IDs
    cursor.execute("""
        DELETE FROM sqlite_sequence
        WHERE name IN ('appointments', 'students', 'mentors')
    """)

    conn.commit()

    print("Old records deleted successfully!")
    print("Database tables are safe.")
    print("You can now register new mentors and students.")

except sqlite3.Error as e:
    conn.rollback()
    print("Error:", e)

finally:
    conn.close()
