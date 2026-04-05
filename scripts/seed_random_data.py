"""
Demo data: departments (panel PRN prefixes), faculty, students (126224xxxx CSE, etc.),
courses, sections, enrollments, attendance, exams, results, assignments.

Run:  python scripts/seed_random_data.py
"""
from __future__ import annotations

import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import get_connection

FIRST_NAMES = (
    "Aarav", "Vihaan", "Aditya", "Ananya", "Diya", "Ishaan", "Kavya", "Neha",
    "Rohan", "Saanvi", "Arjun", "Meera", "Kabir", "Pari", "Yash", "Zara",
)
LAST_NAMES = (
    "Sharma", "Verma", "Patel", "Singh", "Reddy", "Iyer", "Nair", "Kapoor",
    "Malhotra", "Chopra", "Desai", "Joshi", "Kulkarni", "Menon", "Pillai",
)


def ensure_department(cur, name: str, prefix: str) -> int:
    cur.execute("SELECT dept_id FROM department WHERE dept_name = %s", (name,))
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE department SET prn_prefix = COALESCE(prn_prefix, %s) WHERE dept_id = %s",
            (prefix, row["dept_id"]),
        )
        return row["dept_id"]
    cur.execute(
        "INSERT INTO department (dept_name, prn_prefix) VALUES (%s, %s) RETURNING dept_id",
        (name, prefix),
    )
    return cur.fetchone()["dept_id"]


def faculty_id(cur, name: str, email: str, dept_id: int, designation: str) -> int:
    cur.execute("SELECT faculty_id FROM faculty WHERE email = %s", (email,))
    row = cur.fetchone()
    if row:
        return row["faculty_id"]
    cur.execute(
        """
        INSERT INTO faculty (name, email, phone, dept_id, designation, salary)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING faculty_id
        """,
        (
            name,
            email,
            f"555-{random.randint(1000, 9999)}",
            dept_id,
            designation,
            random.randint(90000, 150000),
        ),
    )
    return cur.fetchone()["faculty_id"]


def insert_student(cur, prn: str, name: str, email: str, dept_id: int, year: int) -> int | None:
    cur.execute("SELECT student_id FROM student WHERE prn = %s", (prn,))
    row = cur.fetchone()
    if row:
        return row["student_id"]
    cur.execute(
        """
        INSERT INTO student (prn, name, email, phone, dob, dept_id, enrollment_year, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'active') RETURNING student_id
        """,
        (
            prn,
            name,
            email,
            f"555-{random.randint(2000, 9999)}",
            date(2003, random.randint(1, 12), random.randint(1, 28)),
            dept_id,
            year,
        ),
    )
    return cur.fetchone()["student_id"]


def course_id(cur, title: str, credits: int, dept_id: int, ctype: str) -> int:
    cur.execute(
        "SELECT course_id FROM course WHERE course_name = %s AND dept_id = %s",
        (title, dept_id),
    )
    row = cur.fetchone()
    if row:
        return row["course_id"]
    cur.execute(
        """
        INSERT INTO course (course_name, credits, dept_id, course_type)
        VALUES (%s, %s, %s, %s) RETURNING course_id
        """,
        (title, credits, dept_id, ctype),
    )
    return cur.fetchone()["course_id"]


def section_id(cur, course_id: int, fac_id: int, semester: int, year: int, room: str) -> int:
    cur.execute(
        """
        SELECT section_id FROM section
        WHERE course_id = %s AND semester = %s AND year = %s AND COALESCE(room_no,'') = %s
        """,
        (course_id, semester, year, room),
    )
    row = cur.fetchone()
    if row:
        return row["section_id"]
    cur.execute(
        """
        INSERT INTO section (course_id, faculty_id, semester, year, room_no)
        VALUES (%s, %s, %s, %s, %s) RETURNING section_id
        """,
        (course_id, fac_id, semester, year, room),
    )
    return cur.fetchone()["section_id"]


def enroll(cur, student_id: int, sec_id: int) -> None:
    cur.execute(
        """
        INSERT INTO enrollment (student_id, section_id)
        VALUES (%s, %s) ON CONFLICT (student_id, section_id) DO NOTHING
        """,
        (student_id, sec_id),
    )


def attendance_if_missing(cur, enrollment_id: int, d: date, status: str) -> None:
    cur.execute(
        """
        SELECT 1 FROM attendance WHERE enrollment_id = %s AND attendance_date = %s
        """,
        (enrollment_id, d),
    )
    if cur.fetchone():
        return
    cur.execute(
        """
        INSERT INTO attendance (enrollment_id, attendance_date, status)
        VALUES (%s, %s, %s)
        """,
        (enrollment_id, d, status),
    )


def main() -> None:
    random.seed(42)
    conn = get_connection()
    cur = conn.cursor()

    cse = ensure_department(cur, "Computer Science", "126224")
    ece = ensure_department(cur, "Electronics & Communication", "126225")
    mech = ensure_department(cur, "Mechanical Engineering", "126226")

    f_cse1 = faculty_id(cur, "Dr. Rao", "rao.cse@uni.edu", cse, "Professor")
    f_cse2 = faculty_id(cur, "Dr. Menon", "menon.cse@uni.edu", cse, "Associate Professor")
    f_ece = faculty_id(cur, "Dr. Bose", "bose.ece@uni.edu", ece, "Professor")
    f_mech = faculty_id(cur, "Dr. Khan", "khan.mech@uni.edu", mech, "Professor")

    for i in range(10, 25):
        prn = f"126224{i:04d}"
        fn, ln = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
        insert_student(
            cur, prn, f"{fn} {ln}", f"{fn.lower()}.{ln.lower()}{i}@uni.edu", cse, 2024
        )

    for i in range(1, 11):
        prn = f"126225{i:04d}"
        fn, ln = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
        insert_student(
            cur, prn, f"{fn} {ln}", f"{fn.lower()}.ece{i}@uni.edu", ece, 2024
        )

    for i in range(1, 9):
        prn = f"126226{i:04d}"
        fn, ln = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
        insert_student(
            cur, prn, f"{fn} {ln}", f"{fn.lower()}.mech{i}@uni.edu", mech, 2024
        )

    co_db = course_id(cur, "Database Systems", 4, cse, "core")
    co_dsa = course_id(cur, "Data Structures", 4, cse, "core")
    co_net = course_id(cur, "Computer Networks", 3, cse, "elective")
    co_digi = course_id(cur, "Digital Logic", 3, ece, "core")
    co_th = course_id(cur, "Thermodynamics", 3, mech, "core")

    sec_db = section_id(cur, co_db, f_cse1, 1, 2024, "CS-A101")
    sec_dsa = section_id(cur, co_dsa, f_cse2, 1, 2024, "CS-B102")
    sec_net = section_id(cur, co_net, f_cse1, 2, 2024, "CS-LAB1")
    sec_digi = section_id(cur, co_digi, f_ece, 1, 2024, "EC-201")
    sec_th = section_id(cur, co_th, f_mech, 1, 2024, "ME-105")

    cur.execute("SELECT student_id FROM student WHERE dept_id = %s", (cse,))
    cse_sids = [r["student_id"] for r in cur.fetchall()]
    cur.execute("SELECT student_id FROM student WHERE dept_id = %s", (ece,))
    ece_sids = [r["student_id"] for r in cur.fetchall()]
    cur.execute("SELECT student_id FROM student WHERE dept_id = %s", (mech,))
    mech_sids = [r["student_id"] for r in cur.fetchall()]

    for sid in cse_sids:
        enroll(cur, sid, sec_db)
        if random.random() < 0.88:
            enroll(cur, sid, sec_dsa)
        if random.random() < 0.35:
            enroll(cur, sid, sec_net)
    for sid in ece_sids:
        enroll(cur, sid, sec_digi)
    for sid in mech_sids:
        enroll(cur, sid, sec_th)

    cur.execute(
        "SELECT enrollment_id FROM enrollment WHERE section_id IN (%s, %s, %s)",
        (sec_db, sec_dsa, sec_digi),
    )
    enr = [r["enrollment_id"] for r in cur.fetchall()]
    statuses = ("present", "present", "present", "absent", "late")
    today = date.today()
    for eid in enr[: min(80, len(enr))]:
        for offset in range(0, 12, 2):
            attendance_if_missing(
                cur, eid, today - timedelta(days=offset), random.choice(statuses)
            )

    # Exams + results (CSE DB section)
    cur.execute(
        """
        SELECT exam_id FROM exam WHERE section_id = %s AND exam_type = 'midsem' LIMIT 1
        """,
        (sec_db,),
    )
    er = cur.fetchone()
    if er:
        ex_id = er["exam_id"]
    else:
        cur.execute(
            """
            INSERT INTO exam (section_id, exam_type, exam_date, total_marks)
            VALUES (%s, 'midsem', %s, 50) RETURNING exam_id
            """,
            (sec_db, today - timedelta(days=5)),
        )
        ex_id = cur.fetchone()["exam_id"]

    cur.execute(
        "SELECT student_id FROM enrollment WHERE section_id = %s LIMIT 8",
        (sec_db,),
    )
    for r in cur.fetchall():
        sid = r["student_id"]
        marks = random.randint(28, 48)
        cur.execute(
            """
            INSERT INTO result (exam_id, student_id, marks_obtained, grade)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (exam_id, student_id) DO UPDATE SET
                marks_obtained = EXCLUDED.marks_obtained,
                grade = EXCLUDED.grade
            """,
            (ex_id, sid, marks, "A" if marks >= 42 else "B" if marks >= 35 else "C"),
        )

    # Assignments + a few submissions
    cur.execute(
        """
        SELECT assignment_id FROM assignment
        WHERE section_id = %s AND title = 'ER Diagram v1' LIMIT 1
        """,
        (sec_db,),
    )
    ar = cur.fetchone()
    if ar:
        asg_id = ar["assignment_id"]
    else:
        cur.execute(
            """
            INSERT INTO assignment (section_id, title, due_date, max_marks)
            VALUES (%s, 'ER Diagram v1', %s, 20) RETURNING assignment_id
            """,
            (sec_db, today + timedelta(days=7)),
        )
        asg_id = cur.fetchone()["assignment_id"]

    cur.execute(
        "SELECT student_id FROM enrollment WHERE section_id = %s LIMIT 5",
        (sec_db,),
    )
    for r in cur.fetchall():
        cur.execute(
            """
            INSERT INTO submission (assignment_id, student_id, submission_date, marks, status)
            VALUES (%s, %s, %s, %s, 'submitted')
            ON CONFLICT (assignment_id, student_id) DO UPDATE SET
                submission_date = EXCLUDED.submission_date,
                status = EXCLUDED.status
            """,
            (asg_id, r["student_id"], today - timedelta(days=1), None),
        )

    conn.commit()
    conn.close()
    print("Seed complete: departments, students (PRN panels), enrollments, attendance, exams, assignments.")


if __name__ == "__main__":
    main()
