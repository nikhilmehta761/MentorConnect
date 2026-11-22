
from flask import Flask, render_template, request, redirect
from database import create_tables, get_connection
from datetime import datetime, timedelta
import schedule
import threading
import time

app = Flask(__name__)

create_tables()


# ---------------- DATABASE UPDATE ----------------

def update_database():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(appointments)")
    columns = [column[1] for column in cursor.fetchall()]

    if "reminder_sent" not in columns:
        cursor.execute("""
            ALTER TABLE appointments
            ADD COLUMN reminder_sent INTEGER DEFAULT 0
        """)

    conn.commit()
    conn.close()


update_database()


# ---------------- HOME PAGE ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- MENTOR MANAGEMENT ----------------

@app.route("/mentors", methods=["GET", "POST"])
def mentors():

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        name = request.form["name"].strip()
        subject = request.form["subject"].strip()
        email = request.form["email"].strip()
        available_time = request.form["available_time"].strip()

        cursor.execute("""
            INSERT INTO mentors
            (name, subject, email, available_time)
            VALUES (?, ?, ?, ?)
        """, (name, subject, email, available_time))

        conn.commit()
        conn.close()

        return redirect("/mentors")

    cursor.execute("SELECT * FROM mentors")
    mentor_list = cursor.fetchall()

    conn.close()

    return render_template("mentors.html", mentors=mentor_list)


# ---------------- STUDENT REGISTRATION ----------------

@app.route("/students", methods=["GET", "POST"])
def students():

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        name = request.form["name"].strip()
        email = request.form["email"].strip()
        phone = request.form["phone"].strip()

        cursor.execute("""
            INSERT INTO students (name, email, phone)
            VALUES (?, ?, ?)
        """, (name, email, phone))

        conn.commit()
        conn.close()

        return redirect("/students")

    cursor.execute("SELECT * FROM students")
    student_list = cursor.fetchall()

    conn.close()

    return render_template("students.html", students=student_list)


# ---------------- BOOK APPOINTMENT ----------------

@app.route("/book", methods=["GET", "POST"])
def book():

    conn = get_connection()
    cursor = conn.cursor()

    error = None

    if request.method == "POST":

        try:
            student_id = int(request.form["student_id"])
            mentor_id = int(request.form["mentor_id"])
            date = request.form["date"]
            time_value = request.form["time"]

            appointment_datetime = datetime.strptime(
                date + " " + time_value,
                "%Y-%m-%d %H:%M"
            )

            if appointment_datetime <= datetime.now():
                error = "Past date or time par booking nahi ho sakti."

            else:
                cursor.execute(
                    "SELECT id FROM students WHERE id = ?",
                    (student_id,)
                )
                student = cursor.fetchone()

                cursor.execute(
                    "SELECT id FROM mentors WHERE id = ?",
                    (mentor_id,)
                )
                mentor = cursor.fetchone()

                if not student or not mentor:
                    error = "Please select a valid student and mentor."

                else:
                    cursor.execute("""
                        SELECT id FROM appointments
                        WHERE mentor_id = ?
                        AND date = ?
                        AND time = ?
                        AND status = 'Booked'
                    """, (mentor_id, date, time_value))

                    existing = cursor.fetchone()

                    if existing:
                        error = "This mentor already has an appointment at this time."

                    else:
                        cursor.execute("""
                            INSERT INTO appointments
                            (student_id, mentor_id, date, time)
                            VALUES (?, ?, ?, ?)
                        """, (student_id, mentor_id, date, time_value))

                        conn.commit()
                        conn.close()

                        return redirect("/appointments")

        except ValueError:
            error = "Please enter valid appointment details."

    cursor.execute("SELECT * FROM students")
    student_list = cursor.fetchall()

    cursor.execute("SELECT * FROM mentors")
    mentor_list = cursor.fetchall()

    conn.close()

    return render_template(
        "book.html",
        students=student_list,
        mentors=mentor_list,
        error=error
    )


# ---------------- VIEW APPOINTMENTS ----------------

@app.route("/appointments")
def appointments():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            a.id, s.name, m.name, m.subject,
            a.date, a.time, a.status
        FROM appointments a
        JOIN students s ON a.student_id = s.id
        JOIN mentors m ON a.mentor_id = m.id
        ORDER BY a.date, a.time
    """)

    appointment_list = cursor.fetchall()

    conn.close()

    return render_template(
        "appointments.html",
        appointments=appointment_list
    )


# ---------------- CANCEL APPOINTMENT ----------------

@app.route("/cancel/<int:id>", methods=["POST"])
def cancel_appointment(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE appointments
        SET status = 'Cancelled'
        WHERE id = ? AND status = 'Booked'
    """, (id,))

    conn.commit()
    conn.close()

    return redirect("/appointments")


# ---------------- SEND REMINDERS ----------------

def send_reminders():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            a.id, s.name, m.name,
            a.date, a.time
        FROM appointments a
        JOIN students s ON a.student_id = s.id
        JOIN mentors m ON a.mentor_id = m.id
        WHERE a.status = 'Booked'
        AND a.reminder_sent = 0
    """)

    records = cursor.fetchall()
    now = datetime.now()

    for appt_id, student, mentor, date, time_value in records:

        try:
            appointment_time = datetime.strptime(
                date + " " + time_value,
                "%Y-%m-%d %H:%M"
            )

            difference = appointment_time - now

            if timedelta(0) < difference <= timedelta(hours=1):

                print("\n========== APPOINTMENT REMINDER ==========")
                print("Student:", student)
                print("Mentor:", mentor)
                print("Date:", date)
                print("Time:", time_value)
                print("Your appointment is within one hour!")
                print("==========================================\n")

                cursor.execute("""
                    UPDATE appointments
                    SET reminder_sent = 1
                    WHERE id = ?
                """, (appt_id,))

        except ValueError:
            continue

    conn.commit()
    conn.close()


# ---------------- REMINDER SCHEDULER ----------------

def run_scheduler():

    schedule.every(1).minutes.do(send_reminders)

    while True:
        schedule.run_pending()
        time.sleep(1)


# ---------------- VIEW UPCOMING REMINDERS ----------------

@app.route("/reminders")
def reminders():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            s.name, m.name, a.date, a.time,
            a.reminder_sent
        FROM appointments a
        JOIN students s ON a.student_id = s.id
        JOIN mentors m ON a.mentor_id = m.id
        WHERE a.status = 'Booked'
        ORDER BY a.date, a.time
    """)

    reminder_list = cursor.fetchall()

    conn.close()

    return render_template(
        "reminders.html",
        reminders=reminder_list
    )


# ---------------- RUN APPLICATION ----------------

if __name__ == "__main__":

    reminder_thread = threading.Thread(
        target=run_scheduler,
        daemon=True
    )

    reminder_thread.start()

    app.run(debug=True, use_reloader=False)
