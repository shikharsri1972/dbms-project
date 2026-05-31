import os
import webbrowser
from threading import Timer
from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
from mysql.connector import Error
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "super_secret_key" 

# Database Configuration
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "12345678"
DB_NAME = "student_db"

# Image Upload Configuration
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD
        )
        if connection.is_connected():
            cursor = connection.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
            cursor.close()
            connection.close()

        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        if connection.is_connected():
            cursor = connection.cursor()
            # Recreating table to ensure schema alignment (Roll Number as PK + Image column)
            # We check if roll_number exists, if not we recreate.
            cursor.execute("SHOW TABLES LIKE 'students'")
            table_exists = cursor.fetchone()
            
            recreate = False
            if table_exists:
                cursor.execute("DESCRIBE students")
                columns = [col[0] for col in cursor.fetchall()]
                if 'roll_number' not in columns or 'image' not in columns:
                    recreate = True
            else:
                recreate = True

            if recreate:
                cursor.execute("DROP TABLE IF EXISTS students")
                cursor.execute(
                    '''
                    CREATE TABLE students (
                        roll_number VARCHAR(50) PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        email VARCHAR(100) NOT NULL UNIQUE,
                        course VARCHAR(100),
                        image VARCHAR(255) DEFAULT 'default.png'
                    )
                    '''
                )
            connection.commit()
            cursor.close()
            
        return connection
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        return None

@app.route('/')
def index():
    search_query = request.args.get('search', '')
    conn = get_db_connection()
    if not conn:
        return render_template('error.html', error="Database connection failed. Check your MySQL credentials.")
    
    cursor = conn.cursor(dictionary=True)
    if search_query:
        query = "SELECT * FROM students WHERE roll_number LIKE %s OR name LIKE %s"
        cursor.execute(query, (f"%{search_query}%", f"%{search_query}%"))
    else:
        cursor.execute("SELECT * FROM students")
    
    students = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('index.html', students=students, search_query=search_query)

@app.route('/add', methods=['POST'])
def add_student():
    roll_number = request.form['roll_number']
    name = request.form['name']
    email = request.form['email']
    course = request.form['course']
    
    # Handle Image Upload
    image_filename = 'default.png'
    if 'image' in request.files:
        file = request.files['image']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{roll_number}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_filename = filename
    
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO students (roll_number, name, email, course, image) VALUES (%s, %s, %s, %s, %s)", 
                (roll_number, name, email, course, image_filename)
            )
            conn.commit()
            flash('Student Added Successfully!')
        except Error as e:
            flash(f'Error adding student: {e}')
        finally:
            cursor.close()
            conn.close()
        
    return redirect(url_for('index'))

@app.route('/edit/<roll_number>', methods=['GET', 'POST'])
def edit_student(roll_number):
    conn = get_db_connection()
    if not conn:
        return "Database connection failed"

    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        course = request.form['course']
        
        # Handle Image Update
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                image_filename = secure_filename(f"{roll_number}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        try:
            if image_filename:
                cursor.execute(
                    "UPDATE students SET name=%s, email=%s, course=%s, image=%s WHERE roll_number=%s", 
                    (name, email, course, image_filename, roll_number)
                )
            else:
                cursor.execute(
                    "UPDATE students SET name=%s, email=%s, course=%s WHERE roll_number=%s", 
                    (name, email, course, roll_number)
                )
            conn.commit()
            flash('Student Updated Successfully!')
            return redirect(url_for('index'))
        except Error as e:
            flash(f'Error updating student: {e}')
        finally:
            cursor.close()
            conn.close()
    else:
        cursor.execute("SELECT * FROM students WHERE roll_number = %s", (roll_number,))
        student = cursor.fetchone()
        cursor.close()
        conn.close()
        return render_template('edit.html', student=student)

@app.route('/delete/<roll_number>', methods=['GET'])
def delete_student(roll_number):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM students WHERE roll_number = %s", (roll_number,))
            conn.commit()
            flash('Student Deleted Successfully!')
        except Error as e:
            flash(f'Error deleting student: {e}')
        finally:
            cursor.close()
            conn.close()
        
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Automatically open the browser after a short delay
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    
    app.run(debug=True)
