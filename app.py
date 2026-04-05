import os
from datetime import date, timedelta

from flask import Flask, flash, redirect, render_template, request, session, url_for

from db import get_connection
from student_portal import student_bp

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-change-me-in-production")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["ASSIGNMENT_UPLOAD_FOLDER"] = os.path.join(
    app.root_path, "uploads", "assignments"
)
os.makedirs(app.config["ASSIGNMENT_UPLOAD_FOLDER"], exist_ok=True)

app.register_blueprint(student_bp)


def _role():
    return session.get("role", "admin")


def _home_url():
    if _role() == "student":
        return url_for("student.dashboard")
    return url_for("faculty_home")


PUBLIC_ENDPOINTS = frozenset(["login", "static"])


def _resolve_student_pk(cur, form) -> int | None:
    prn = (form.get("student_prn") or "").strip()
    if prn:
        cur.execute("SELECT student_id FROM student WHERE prn = %s", (prn,))
        row = cur.fetchone()
        return row["student_id"] if row else None
    raw = form.get("student_id")
    if raw not in (None, ""):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    return None


@app.before_request
def gate():
    ep = request.endpoint
    if ep is None or ep in PUBLIC_ENDPOINTS:
        return None

    if "user" not in session:
        return redirect(url_for("login"))

    if _role() == "student":
        if request.blueprint == "student" or ep == "logout":
            return None
        return redirect(url_for("student.dashboard"))

    if request.blueprint == "student":
        return redirect(url_for("faculty_home"))

    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(_home_url())

    if request.method == "POST":
        uname = request.form.get("username", "").strip()
        pwd = request.form.get("password", "")

        if not uname or not pwd:
            flash("Please enter both username and password.", "warning")
            return render_template("login.html")

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM app_user WHERE username = %s AND password = %s",
            (uname, pwd),
        )
        user = cur.fetchone()

        if not user:
            conn.close()
            flash("Invalid username or password.", "danger")
            return render_template("login.html")

        display = user["username"]
        sid = user.get("student_id")
        fid = user.get("faculty_id")

        if sid:
            cur.execute("SELECT name FROM student WHERE student_id = %s", (sid,))
            row = cur.fetchone()
            if row:
                display = row["name"]
        elif fid:
            cur.execute("SELECT name FROM faculty WHERE faculty_id = %s", (fid,))
            row = cur.fetchone()
            if row:
                display = row["name"]

        conn.close()

        session["user"] = user["username"]
        session["role"] = user.get("role") or "admin"
        session["student_id"] = sid
        session["faculty_id"] = fid
        session["display_name"] = display

        return redirect(_home_url())

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("login"))


@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))
    return redirect(_home_url())


@app.route("/faculty")
def faculty_home():
    return render_template("faculty/dashboard.html")


# ── helpers ──────────────────────────────────────────────────────────

def _fetch_sections(cur):
    cur.execute(
        """
        SELECT sec.section_id, c.course_name, sec.semester, sec.year, sec.room_no,
               d.dept_name
        FROM section sec
        JOIN course c ON c.course_id = sec.course_id
        JOIN department d ON d.dept_id = c.dept_id
        ORDER BY d.dept_name, sec.year DESC, sec.semester, c.course_name, sec.section_id
        """
    )
    return cur.fetchall()


def _sections_for_session(cur):
    if _role() == "admin":
        return _fetch_sections(cur)
    fid = session.get("faculty_id")
    if not fid:
        return []
    cur.execute(
        """
        SELECT sec.section_id, c.course_name, sec.semester, sec.year, sec.room_no,
               d.dept_name
        FROM section sec
        JOIN course c ON c.course_id = sec.course_id
        JOIN department d ON d.dept_id = c.dept_id
        WHERE sec.faculty_id = %s
        ORDER BY d.dept_name, sec.year DESC, sec.semester, c.course_name, sec.section_id
        """,
        (fid,),
    )
    return cur.fetchall()


def _can_take_attendance_for_section(cur, section_id: int) -> bool:
    if _role() == "admin":
        return True
    fid = session.get("faculty_id")
    if not fid:
        return False
    cur.execute(
        "SELECT 1 FROM section WHERE section_id = %s AND faculty_id = %s",
        (section_id, fid),
    )
    return cur.fetchone() is not None


def _attendance_sheet_rows(cur, section_id: int, adate):
    cur.execute(
        """
        SELECT e.enrollment_id, s.student_id, s.name AS student_name, s.prn,
               att.status AS current_status
        FROM enrollment e
        JOIN student s ON s.student_id = e.student_id
        LEFT JOIN attendance att
          ON att.enrollment_id = e.enrollment_id AND att.attendance_date = %s
        WHERE e.section_id = %s
        ORDER BY s.prn NULLS LAST, s.name
        """,
        (adate, section_id),
    )
    return cur.fetchall()


def _pending_submissions(cur):
    fid = session.get("faculty_id")
    if _role() == "admin":
        where, params = "", ()
    elif fid:
        where, params = "AND sec.faculty_id = %s", (fid,)
    else:
        return []
    cur.execute(
        f"""
        SELECT sub.submission_id, sub.student_id, s.prn AS student_prn,
               s.name AS student_name,
               a.title, a.max_marks, a.assignment_id, c.course_name
        FROM submission sub
        JOIN student s ON s.student_id = sub.student_id
        JOIN assignment a ON a.assignment_id = sub.assignment_id
        JOIN section sec ON sec.section_id = a.section_id
        JOIN course c ON c.course_id = sec.course_id
        WHERE sub.marks IS NULL {where}
        ORDER BY sub.submission_date DESC
        LIMIT 100
        """,
        params,
    )
    return cur.fetchall()


# ── faculty / admin routes ───────────────────────────────────────────

@app.route("/students")
def students():
    conn = get_connection()
    cur = conn.cursor()
    search = request.args.get("search", "")
    dept_id = request.args.get("dept_id", type=int)
    fid = session.get("faculty_id")

    cur.execute(
        """
        SELECT dept_id, dept_name, prn_prefix
        FROM department ORDER BY dept_name
        """
    )
    panels = cur.fetchall()

    if _role() == "admin":
        q = """
            SELECT s.*, d.dept_name
            FROM student s
            LEFT JOIN department d ON s.dept_id = d.dept_id
            WHERE s.name ILIKE %s
        """
        params: list = [f"%{search}%"]
        if dept_id:
            q += " AND s.dept_id = %s"
            params.append(dept_id)
        q += " ORDER BY d.dept_name NULLS LAST, s.prn NULLS LAST, s.name"
        cur.execute(q, tuple(params))
    elif fid:
        q = """
            SELECT DISTINCT s.*, d.dept_name
            FROM student s
            LEFT JOIN department d ON s.dept_id = d.dept_id
            JOIN enrollment e ON e.student_id = s.student_id
            JOIN section sec ON sec.section_id = e.section_id
            WHERE sec.faculty_id = %s AND s.name ILIKE %s
        """
        params = [fid, f"%{search}%"]
        if dept_id:
            q += " AND s.dept_id = %s"
            params.append(dept_id)
        q += " ORDER BY d.dept_name NULLS LAST, s.prn NULLS LAST, s.name"
        cur.execute(q, tuple(params))
    else:
        conn.close()
        return render_template(
            "students.html",
            students=[],
            search=search,
            panels=panels,
            dept_id=dept_id,
        )

    data = cur.fetchall()
    data.sort(
        key=lambda r: (
            r.get("dept_name") or "ZZZ_Unassigned",
            r.get("prn") or "",
            (r.get("name") or "").lower(),
        )
    )
    conn.close()
    return render_template(
        "students.html",
        students=data,
        search=search,
        panels=panels,
        dept_id=dept_id,
    )


@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM department ORDER BY dept_name")
    depts = cur.fetchall()

    if request.method == "POST":
        prn = (request.form.get("prn") or "").strip()
        if not prn:
            conn.close()
            flash("PRN is required (e.g. 1262240002 for CSE).", "danger")
            return render_template("add_student.html", depts=depts)
        cur.execute("SELECT 1 FROM student WHERE prn = %s", (prn,))
        if cur.fetchone():
            conn.close()
            flash("That PRN is already registered.", "danger")
            return render_template("add_student.html", depts=depts)
        cur.execute(
            "SELECT prn_prefix FROM department WHERE dept_id = %s",
            (request.form["dept_id"],),
        )
        pref_row = cur.fetchone()
        pref = (pref_row or {}).get("prn_prefix")
        if pref:
            p = str(pref)
            if len(prn) != 10 or not prn.startswith(p):
                conn.close()
                flash(
                    f"PRN must be 10 digits starting with department prefix {p} (e.g. {p}0001).",
                    "danger",
                )
                return render_template("add_student.html", depts=depts)
        dob = request.form.get("dob") or None
        phone = request.form.get("phone") or None
        status = request.form.get("status") or "active"
        cur.execute(
            """
            INSERT INTO student (prn, name, email, phone, dob, dept_id, enrollment_year, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                prn,
                request.form["name"],
                request.form.get("email") or None,
                phone,
                dob,
                request.form["dept_id"],
                request.form.get("year") or None,
                status,
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("students"))

    conn.close()
    return render_template("add_student.html", depts=depts)


@app.route("/enroll", methods=["GET", "POST"])
def enroll():
    conn = get_connection()
    cur = conn.cursor()
    search = request.args.get("search", "")
    fid = session.get("faculty_id")

    if _role() == "admin":
        cur.execute(
            """
            SELECT s.*
            FROM student s
            LEFT JOIN department d ON d.dept_id = s.dept_id
            WHERE s.name ILIKE %s
            ORDER BY d.dept_name NULLS LAST, s.prn NULLS LAST, s.name
            """,
            (f"%{search}%",),
        )
    elif fid:
        cur.execute(
            """
            SELECT DISTINCT s.*
            FROM student s
            LEFT JOIN department d ON d.dept_id = s.dept_id
            JOIN enrollment e ON e.student_id = s.student_id
            JOIN section sec ON sec.section_id = e.section_id
            WHERE sec.faculty_id = %s AND s.name ILIKE %s
            ORDER BY d.dept_name NULLS LAST, s.prn NULLS LAST, s.name
            """,
            (fid, f"%{search}%"),
        )
    else:
        conn.close()
        return render_template("enroll.html", students=[], sections=[], search=search)

    stud_list = cur.fetchall()
    sections = _sections_for_session(cur)

    if request.method == "POST":
        cur.execute(
            """
            INSERT INTO enrollment (student_id, section_id)
            VALUES (%s, %s)
            ON CONFLICT (student_id, section_id) DO NOTHING
            """,
            (request.form["student_id"], request.form["section_id"]),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("students"))

    conn.close()
    return render_template(
        "enroll.html", students=stud_list, sections=sections, search=search
    )


@app.route("/attendance", methods=["GET", "POST"])
def attendance():
    conn = get_connection()
    cur = conn.cursor()
    sections = _sections_for_session(cur)

    section_id = request.args.get("section_id", type=int)
    if request.method == "POST":
        section_id = request.form.get("section_id", type=int)
    raw_date = (request.args.get("date") if request.method == "GET" else request.form.get("date")) or ""
    try:
        adate = date.fromisoformat(raw_date) if raw_date else date.today()
    except ValueError:
        adate = date.today()

    sheet = []
    if section_id:
        if _can_take_attendance_for_section(cur, section_id):
            sheet = _attendance_sheet_rows(cur, section_id, adate)
        else:
            flash("You cannot record attendance for that section.", "danger")
            section_id = None

    if request.method == "POST" and request.form.get("bulk_save") == "1":
        if not section_id or not _can_take_attendance_for_section(cur, section_id):
            conn.close()
            flash("Invalid section.", "danger")
            return redirect(url_for("attendance"))

        all_eids = [int(x) for x in request.form.getlist("all_eid") if x.strip().isdigit()]
        present_eids = {int(x) for x in request.form.getlist("present") if str(x).isdigit()}
        late_eids = {int(x) for x in request.form.getlist("late") if str(x).isdigit()}

        cur.execute(
            "SELECT enrollment_id FROM enrollment WHERE section_id = %s",
            (section_id,),
        )
        valid = {r["enrollment_id"] for r in cur.fetchall()}
        all_eids = [e for e in all_eids if e in valid]

        saved = 0
        for eid in all_eids:
            if eid in late_eids:
                status = "late"
            elif eid in present_eids:
                status = "present"
            else:
                status = "absent"
            cur.execute(
                "DELETE FROM attendance WHERE enrollment_id = %s AND attendance_date = %s",
                (eid, adate),
            )
            cur.execute(
                """
                INSERT INTO attendance (enrollment_id, attendance_date, status)
                VALUES (%s, %s, %s)
                """,
                (eid, adate, status),
            )
            saved += 1
        conn.commit()
        conn.close()
        flash(f"Saved attendance for {saved} students on {adate.isoformat()}.", "success")
        return redirect(
            url_for("attendance", section_id=section_id, date=adate.isoformat())
        )

    conn.close()
    return render_template(
        "attendance.html",
        sections=sections,
        section_id=section_id,
        adate=adate,
        prev_date=(adate - timedelta(days=1)).isoformat(),
        next_date=(adate + timedelta(days=1)).isoformat(),
        sheet=sheet,
    )


@app.route("/exams", methods=["GET", "POST"])
def exams():
    conn = get_connection()
    cur = conn.cursor()
    sections = _sections_for_session(cur)

    if request.method == "POST":
        cur.execute(
            """
            INSERT INTO exam (section_id, exam_type, exam_date, total_marks)
            VALUES (%s, %s, %s, %s)
            """,
            (
                request.form["section_id"],
                request.form["exam_type"],
                request.form["date"],
                request.form["total"],
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("exams"))

    conn.close()
    return render_template("exams.html", sections=sections)


@app.route("/results", methods=["POST"])
def results():
    conn = get_connection()
    cur = conn.cursor()
    exam_id = request.form["exam_id"]

    if _role() != "admin":
        fid = session.get("faculty_id")
        cur.execute(
            """
            SELECT 1 FROM exam e JOIN section sec ON sec.section_id = e.section_id
            WHERE e.exam_id = %s AND sec.faculty_id = %s
            """,
            (exam_id, fid),
        )
        if not cur.fetchone():
            conn.close()
            flash("You cannot grade results for that exam.", "danger")
            return redirect(url_for("exams"))

    stu_pk = _resolve_student_pk(cur, request.form)
    if not stu_pk:
        conn.close()
        flash("Enter a valid student PRN (or numeric internal ID).", "danger")
        return redirect(url_for("exams"))

    grade = request.form.get("grade") or None
    cur.execute(
        """
        INSERT INTO result (exam_id, student_id, marks_obtained, grade)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (exam_id, student_id) DO UPDATE SET
            marks_obtained = EXCLUDED.marks_obtained,
            grade = EXCLUDED.grade
        """,
        (exam_id, stu_pk, request.form["marks"], grade),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("students"))


@app.route("/assignments", methods=["GET", "POST"])
def assignments():
    conn = get_connection()
    cur = conn.cursor()
    sections = _sections_for_session(cur)
    pending = _pending_submissions(cur)

    if request.method == "POST":
        cur.execute(
            """
            INSERT INTO assignment (section_id, title, due_date, max_marks)
            VALUES (%s, %s, %s, %s)
            """,
            (
                request.form["section_id"],
                request.form["title"],
                request.form["due_date"],
                request.form["max"],
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("assignments"))

    conn.close()
    return render_template("assignments.html", sections=sections, pending=pending)


@app.route("/grade_submission", methods=["POST"])
def grade_submission():
    conn = get_connection()
    cur = conn.cursor()
    sid = request.form.get("submission_id")
    marks = request.form.get("marks")
    if not sid or marks in (None, ""):
        conn.close()
        flash("Submission id and marks are required.", "warning")
        return redirect(url_for("assignments"))

    fid = session.get("faculty_id")
    if _role() == "admin":
        cur.execute(
            """
            UPDATE submission sub SET marks = %s
            FROM assignment a JOIN section sec ON sec.section_id = a.section_id
            WHERE sub.submission_id = %s AND sub.assignment_id = a.assignment_id
            """,
            (marks, sid),
        )
    elif fid:
        cur.execute(
            """
            UPDATE submission sub SET marks = %s
            FROM assignment a JOIN section sec ON sec.section_id = a.section_id
            WHERE sub.submission_id = %s AND sub.assignment_id = a.assignment_id
              AND sec.faculty_id = %s
            """,
            (marks, sid, fid),
        )
    else:
        conn.close()
        flash("Could not update that submission.", "danger")
        return redirect(url_for("assignments"))

    if cur.rowcount == 0:
        flash("Could not update that submission.", "danger")
    else:
        flash("Marks saved.", "success")
    conn.commit()
    conn.close()
    return redirect(url_for("assignments"))


@app.route("/submit", methods=["POST"])
def submit():
    if _role() not in ("faculty", "admin"):
        flash("Use the student portal to submit your work.", "info")
        return redirect(url_for("student.assignments"))

    conn = get_connection()
    cur = conn.cursor()
    stu_pk = _resolve_student_pk(cur, request.form)
    if not stu_pk:
        conn.close()
        flash("Enter a valid student PRN (or numeric internal ID).", "danger")
        return redirect(url_for("assignments"))
    marks = request.form.get("marks") or None
    cur.execute(
        """
        INSERT INTO submission (assignment_id, student_id, submission_date, marks, status)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (assignment_id, student_id) DO UPDATE SET
            submission_date = EXCLUDED.submission_date,
            marks = COALESCE(EXCLUDED.marks, submission.marks),
            status = EXCLUDED.status
        """,
        (
            request.form["assignment_id"],
            stu_pk,
            request.form["date"],
            marks,
            request.form["status"],
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("students"))


@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    conn = get_connection()
    cur = conn.cursor()
    fid = session.get("faculty_id")

    if _role() == "admin":
        cur.execute(
            """
            SELECT s.*, d.dept_name
            FROM student s
            LEFT JOIN department d ON d.dept_id = s.dept_id
            ORDER BY d.dept_name NULLS LAST, s.prn NULLS LAST, s.name
            """
        )
        stud_list = cur.fetchall()
    elif fid:
        cur.execute(
            """
            SELECT DISTINCT s.*, d.dept_name
            FROM student s
            LEFT JOIN department d ON d.dept_id = s.dept_id
            JOIN enrollment e ON e.student_id = s.student_id
            JOIN section sec ON sec.section_id = e.section_id
            WHERE sec.faculty_id = %s
            ORDER BY d.dept_name NULLS LAST, s.prn NULLS LAST, s.name
            """,
            (fid,),
        )
        stud_list = cur.fetchall()
    else:
        stud_list = []

    sections = _sections_for_session(cur)

    if request.method == "POST":
        cur.execute(
            """
            INSERT INTO feedback (student_id, section_id, rating, comments)
            VALUES (%s, %s, %s, %s)
            """,
            (
                request.form["student_id"],
                request.form["section_id"],
                request.form["rating"],
                request.form.get("comments") or None,
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("faculty_home"))

    conn.close()
    return render_template("feedback.html", students=stud_list, sections=sections)


@app.route("/dashboard")
def dashboard():
    fid = session.get("faculty_id")
    if _role() != "admin" and not fid:
        return render_template("dashboard.html", data=[])

    conn = get_connection()
    cur = conn.cursor()

    if _role() == "admin":
        cur.execute(
            """
            SELECT status, COUNT(*)::bigint AS count
            FROM attendance GROUP BY status ORDER BY status
            """
        )
    else:
        cur.execute(
            """
            SELECT att.status, COUNT(*)::bigint AS count
            FROM attendance att
            JOIN enrollment e ON e.enrollment_id = att.enrollment_id
            JOIN section sec ON sec.section_id = e.section_id
            WHERE sec.faculty_id = %s
            GROUP BY att.status ORDER BY att.status
            """,
            (fid,),
        )
    data = cur.fetchall()
    conn.close()
    return render_template(
        "dashboard.html",
        data=[{"status": r["status"], "count": int(r["count"])} for r in data],
    )


if __name__ == "__main__":
    app.run(debug=True)
