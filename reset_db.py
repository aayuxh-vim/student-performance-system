import os
from db import get_connection

def reset_db():
    conn = get_connection()
    cur = conn.cursor()
    
    print("Dropping public schema...")
    cur.execute("DROP SCHEMA public CASCADE;")
    cur.execute("CREATE SCHEMA public;")
    
    print("Creating tables (8 total including audit log)...")
    
    # 1. app_user
    cur.execute("""
        CREATE TABLE app_user (
            user_id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
    """)
    
    # 2. department
    cur.execute("""
        CREATE TABLE department (
            department_id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );
    """)

    # 3. teacher
    cur.execute("""
        CREATE TABLE teacher (
            teacher_id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            department_id INT REFERENCES department(department_id) ON DELETE SET NULL
        );
    """)

    # 4. student
    cur.execute("""
        CREATE TABLE student (
            student_id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            department_id INT REFERENCES department(department_id) ON DELETE SET NULL
        );
    """)

    # 5. course
    cur.execute("""
        CREATE TABLE course (
            course_id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            teacher_id INT REFERENCES teacher(teacher_id) ON DELETE SET NULL
        );
    """)

    # 6. enrollment
    cur.execute("""
        CREATE TABLE enrollment (
            enrollment_id SERIAL PRIMARY KEY,
            student_id INT NOT NULL REFERENCES student(student_id) ON DELETE CASCADE,
            course_id INT NOT NULL REFERENCES course(course_id) ON DELETE CASCADE,
            UNIQUE(student_id, course_id)
        );
    """)

    # 7. grade
    cur.execute("""
        CREATE TABLE grade (
            grade_id SERIAL PRIMARY KEY,
            enrollment_id INT NOT NULL REFERENCES enrollment(enrollment_id) ON DELETE CASCADE,
            score NUMERIC(5, 2) NOT NULL
        );
    """)
    
    # 8. audit_log
    cur.execute("""
        CREATE TABLE audit_log (
            log_id SERIAL PRIMARY KEY,
            action_name TEXT NOT NULL,
            table_name TEXT NOT NULL,
            record_id INT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    print("Creating PL/pgSQL Function and Trigger...")
    # PLSQL Function
    cur.execute("""
        CREATE OR REPLACE FUNCTION get_student_average(p_student_id INT) 
        RETURNS NUMERIC AS $$
        DECLARE
            avg_score NUMERIC;
        BEGIN
            SELECT AVG(g.score) INTO avg_score
            FROM grade g
            JOIN enrollment e ON g.enrollment_id = e.enrollment_id
            WHERE e.student_id = p_student_id;
            
            RETURN COALESCE(avg_score, 0);
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Trigger Function
    cur.execute("""
        CREATE OR REPLACE FUNCTION log_grade_insert() 
        RETURNS TRIGGER AS $$
        BEGIN
            INSERT INTO audit_log(action_name, table_name, record_id)
            VALUES ('INSERT', 'grade', NEW.grade_id);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Trigger
    cur.execute("""
        CREATE TRIGGER after_grade_insert
        AFTER INSERT ON grade
        FOR EACH ROW
        EXECUTE FUNCTION log_grade_insert();
    """)
    
    print("Executing DCL (Grants)...")
    cur.execute("GRANT ALL ON SCHEMA public TO postgres;")
    cur.execute("GRANT ALL ON SCHEMA public TO public;")
    cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO public;")

    print("Inserting default admin user and seed data (DML)...")
    cur.execute("INSERT INTO app_user (username, password) VALUES ('admin', 'admin');")
    
    cur.execute("INSERT INTO department (name) VALUES ('Computer Science'), ('Mathematics') RETURNING department_id;")
    dept_ids = [row['department_id'] for row in cur.fetchall()]
    
    if len(dept_ids) >= 2:
        cur.execute("INSERT INTO teacher (name, email, department_id) VALUES ('Dr. Alan Turing', 'alan@cs.edu', %s) RETURNING teacher_id;", (dept_ids[0],))
        t1_id = cur.fetchone()['teacher_id']
        
        cur.execute("INSERT INTO course (name, teacher_id) VALUES ('Algorithms 101', %s) RETURNING course_id;", (t1_id,))
        c1_id = cur.fetchone()['course_id']
        
        cur.execute("INSERT INTO student (name, email, department_id) VALUES ('Grace Hopper', 'grace@cs.edu', %s) RETURNING student_id;", (dept_ids[0],))
        s1_id = cur.fetchone()['student_id']
        
        cur.execute("INSERT INTO enrollment (student_id, course_id) VALUES (%s, %s) RETURNING enrollment_id;", (s1_id, c1_id))
        e1_id = cur.fetchone()['enrollment_id']
        
        # This will fire the trigger
        cur.execute("INSERT INTO grade (enrollment_id, score) VALUES (%s, %s);", (e1_id, 98.5))

    conn.commit()
    conn.close()
    print("Database reset successfully with triggers and functions!")

if __name__ == "__main__":
    reset_db()
