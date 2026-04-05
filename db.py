import pymysql

def get_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="aayush@7",
        database="student_analytics",
        cursorclass=pymysql.cursors.DictCursor
    )
