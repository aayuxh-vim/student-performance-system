import os
from flask import Flask, flash, redirect, render_template, request, session, url_for
from db import get_connection

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-change-me-in-production")

@app.before_request
def gate():
    if request.endpoint in ("login", "static"):
        return None
    if "user" not in session:
        return redirect(url_for("login"))
    return None

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        uname = request.form.get("username", "").strip()
        pwd = request.form.get("password", "")
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM app_user WHERE username = %s AND password = %s", (uname, pwd))
        user = cur.fetchone()
        conn.close()
        if not user:
            flash("Invalid username or password.", "danger")
            return render_template("login.html")
        session["user"] = user["username"]
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("login"))

@app.route("/")
def index():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT count(*) as cnt FROM department")
    dept_count = cur.fetchone()['cnt']
    cur.execute("SELECT count(*) as cnt FROM teacher")
    teacher_count = cur.fetchone()['cnt']
    cur.execute("SELECT count(*) as cnt FROM course")
    course_count = cur.fetchone()['cnt']
    cur.execute("SELECT count(*) as cnt FROM student")
    student_count = cur.fetchone()['cnt']
    
    cur.execute("""
        SELECT s.student_id, s.name, s.email, d.name as dept_name
        FROM student s
        LEFT JOIN department d ON s.department_id = d.department_id
        ORDER BY s.name
    """)
    students = cur.fetchall()
    conn.close()
    return render_template("dashboard.html", 
                           dept_count=dept_count, teacher_count=teacher_count, 
                           course_count=course_count, student_count=student_count, 
                           students=students)

# ---- Departments ----
@app.route("/add_department", methods=["GET", "POST"])
def add_department():
    if request.method == "POST":
        name = request.form.get("name")
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO department (name) VALUES (%s)", (name,))
            conn.commit()
            flash("Department added!", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for('index'))
    return render_template("add_generic.html", title="Add Department", fields=[{"name": "name", "label": "Department Name"}])

# ---- Teachers ----
@app.route("/add_teacher", methods=["GET", "POST"])
def add_teacher():
    conn = get_connection()
    cur = conn.cursor()
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        dept_id = request.form.get("department_id") or None
        cur.execute("INSERT INTO teacher (name, email, department_id) VALUES (%s, %s, %s)", (name, email, dept_id))
        conn.commit()
        conn.close()
        flash("Teacher added!", "success")
        return redirect(url_for('index'))
    cur.execute("SELECT * FROM department")
    depts = cur.fetchall()
    conn.close()
    return render_template("add_teacher.html", depts=depts)

# ---- Courses ----
@app.route("/add_course", methods=["GET", "POST"])
def add_course():
    conn = get_connection()
    cur = conn.cursor()
    if request.method == "POST":
        name = request.form.get("name")
        teacher_id = request.form.get("teacher_id") or None
        cur.execute("INSERT INTO course (name, teacher_id) VALUES (%s, %s)", (name, teacher_id))
        conn.commit()
        conn.close()
        flash("Course added!", "success")
        return redirect(url_for('index'))
    cur.execute("SELECT * FROM teacher")
    teachers = cur.fetchall()
    conn.close()
    return render_template("add_course.html", teachers=teachers)

# ---- Students ----
@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    conn = get_connection()
    cur = conn.cursor()
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        dept_id = request.form.get("department_id") or None
        cur.execute("INSERT INTO student (name, email, department_id) VALUES (%s, %s, %s)", (name, email, dept_id))
        conn.commit()
        conn.close()
        flash("Student added successfully!", "success")
        return redirect(url_for("index"))
    cur.execute("SELECT * FROM department")
    depts = cur.fetchall()
    conn.close()
    return render_template("add_student.html", depts=depts)

@app.route("/student/<int:student_id>")
def student_detail(student_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.*, d.name as dept_name 
        FROM student s LEFT JOIN department d ON s.department_id = d.department_id 
        WHERE s.student_id = %s
    """, (student_id,))
    student = cur.fetchone()
    if not student:
        conn.close()
        flash("Student not found", "danger")
        return redirect(url_for("index"))
        
    cur.execute("""
        SELECT e.enrollment_id, c.name as course_name, t.name as teacher_name, g.score 
        FROM enrollment e 
        JOIN course c ON e.course_id = c.course_id 
        LEFT JOIN teacher t ON c.teacher_id = t.teacher_id
        LEFT JOIN grade g ON e.enrollment_id = g.enrollment_id
        WHERE e.student_id = %s
    """, (student_id,))
    enrollments = cur.fetchall()
    conn.close()
    return render_template("student_detail.html", student=student, enrollments=enrollments)

# ---- Enrollments ----
@app.route("/enroll/<int:student_id>", methods=["GET", "POST"])
def enroll(student_id):
    conn = get_connection()
    cur = conn.cursor()
    if request.method == "POST":
        course_id = request.form.get("course_id")
        try:
            cur.execute("INSERT INTO enrollment (student_id, course_id) VALUES (%s, %s)", (student_id, course_id))
            conn.commit()
            flash("Enrolled successfully!", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")
        conn.close()
        return redirect(url_for("student_detail", student_id=student_id))
    cur.execute("SELECT * FROM student WHERE student_id = %s", (student_id,))
    student = cur.fetchone()
    cur.execute("SELECT * FROM course")
    courses = cur.fetchall()
    conn.close()
    return render_template("enroll.html", student=student, courses=courses)

# ---- Grades ----
@app.route("/add_grade/<int:enrollment_id>", methods=["GET", "POST"])
def add_grade(enrollment_id):
    conn = get_connection()
    cur = conn.cursor()
    if request.method == "POST":
        score = request.form.get("score")
        cur.execute("INSERT INTO grade (enrollment_id, score) VALUES (%s, %s)", (enrollment_id, score))
        cur.execute("SELECT student_id FROM enrollment WHERE enrollment_id = %s", (enrollment_id,))
        student_id = cur.fetchone()['student_id']
        conn.commit()
        conn.close()
        flash("Grade added successfully!", "success")
        return redirect(url_for("student_detail", student_id=student_id))
    cur.execute("""
        SELECT e.enrollment_id, c.name as course_name, s.name as student_name, s.student_id
        FROM enrollment e
        JOIN course c ON e.course_id = c.course_id
        JOIN student s ON e.student_id = s.student_id
        WHERE e.enrollment_id = %s
    """, (enrollment_id,))
    data = cur.fetchone()
    conn.close()
    if not data:
        flash("Enrollment not found", "danger")
        return redirect(url_for("index"))
    return render_template("add_grade.html", data=data)

if __name__ == "__main__":
    app.run(debug=True)
