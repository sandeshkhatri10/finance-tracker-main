from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

app = Flask(__name__)

# Database setup
def init_db():
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS income
                     (id INTEGER PRIMARY KEY, date TEXT, amount REAL, category TEXT, description TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS expenses
                     (id INTEGER PRIMARY KEY, date TEXT, amount REAL, category TEXT, description TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS workouts
                     (id INTEGER PRIMARY KEY, date TEXT, body_parts TEXT, duration INTEGER, notes TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS tasks
                     (id INTEGER PRIMARY KEY, task TEXT, status TEXT DEFAULT 'Pending')''')
        conn.commit()

init_db()

# Helper functions
def calculate_weekly_totals():
    today = datetime.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        
        # Calculate weekly income
        c.execute('''SELECT SUM(amount) FROM income WHERE date BETWEEN ? AND ?''', 
                  (start_of_week.strftime('%Y-%m-%d'), end_of_week.strftime('%Y-%m-%d')))
        weekly_income = c.fetchone()[0] or 0

        # Calculate weekly expenses
        c.execute('''SELECT SUM(amount) FROM expenses WHERE date BETWEEN ? AND ?''', 
                  (start_of_week.strftime('%Y-%m-%d'), end_of_week.strftime('%Y-%m-%d')))
        weekly_expenses = c.fetchone()[0] or 0

    weekly_savings = weekly_income - weekly_expenses
    return weekly_income, weekly_expenses, weekly_savings

# Routes
@app.route('/')
def home():
    # Fetch income and expense entries for the week
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        # Get all income entries
        c.execute('SELECT * FROM income')
        income_entries = c.fetchall()
        
        # Get all expense entries
        c.execute('SELECT * FROM expenses')
        expense_entries = c.fetchall()

    # Calculate weekly totals from the entries
    weekly_income = sum([entry[2] for entry in income_entries])
    weekly_expenses = sum([entry[2] for entry in expense_entries])
    weekly_savings = weekly_income - weekly_expenses
    
    labels = ['Income', 'Expenses']
    data = [weekly_income, weekly_expenses]
    
    return render_template('home.html', 
                           weekly_income=weekly_income, 
                           weekly_expenses=weekly_expenses, 
                           weekly_savings=weekly_savings,
                           labels=labels, 
                           data=data,
                           income_entries=income_entries,
                           expense_entries=expense_entries)

@app.route('/statements', methods=['GET', 'POST'])
def statements():
    if request.method == 'POST':
        entry_type = request.form['entry_type']
        date = request.form['date']
        amount = float(request.form['amount'])
        category = request.form['category']
        description = request.form['description']

        with sqlite3.connect('database.db') as conn:
            c = conn.cursor()
            if entry_type == 'income':
                c.execute('INSERT INTO income (date, amount, category, description) VALUES (?, ?, ?, ?)',
                          (date, amount, category, description))
            else:
                c.execute('INSERT INTO expenses (date, amount, category, description) VALUES (?, ?, ?, ?)',
                          (date, amount, category, description))
            conn.commit()

        return redirect(url_for('statements'))

    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM income')
        income_entries = c.fetchall()
        c.execute('SELECT * FROM expenses')
        expense_entries = c.fetchall()

    return render_template('statements.html', income_entries=income_entries, expense_entries=expense_entries)

@app.route('/gym', methods=['GET', 'POST'])
def gym_tracker():
    if request.method == 'POST':
        date = request.form['date']
        body_parts = request.form['body_parts']
        duration = int(request.form['duration'])
        notes = request.form['notes']

        with sqlite3.connect('database.db') as conn:
            c = conn.cursor()
            c.execute('INSERT INTO workouts (date, body_parts, duration, notes) VALUES (?, ?, ?, ?)',
                      (date, body_parts, duration, notes))
            conn.commit()

        return redirect(url_for('gym_tracker'))

    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM workouts ORDER BY date DESC')
        workouts = c.fetchall()

    return render_template('gym_tracker.html', workouts=workouts)

@app.route('/todo', methods=['GET', 'POST'])
def todo():
    if request.method == 'POST':
        if 'add_task' in request.form:
            task = request.form['task']
            with sqlite3.connect('database.db') as conn:
                c = conn.cursor()
                c.execute('INSERT INTO tasks (task) VALUES (?)', (task,))
                conn.commit()
        elif 'delete_task' in request.form:
            task_id = request.form['task_id']
            with sqlite3.connect('database.db') as conn:
                c = conn.cursor()
                c.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
                conn.commit()
        elif 'update_task' in request.form:
            task_id = request.form['task_id']
            new_task = request.form['new_task']
            with sqlite3.connect('database.db') as conn:
                c = conn.cursor()
                c.execute('UPDATE tasks SET task = ? WHERE id = ?', (new_task, task_id))
                conn.commit()

        return redirect(url_for('todo'))

    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM tasks ORDER BY id DESC')
        tasks = c.fetchall()

    return render_template('todo.html', tasks=tasks)

# Route to download the statement as a PDF
@app.route('/download_statement', methods=['GET'])
def download_statement():
    # Get income and expense data from the database
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM income')
        income_entries = c.fetchall()
        c.execute('SELECT * FROM expenses')
        expense_entries = c.fetchall()

    # Create a PDF in memory using BytesIO
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(200, height - 40, "Income and Expense Statement")

    # Income Table
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 80, "Income Entries:")
    y_position = height - 100
    c.setFont("Helvetica", 10)
    for entry in income_entries:
        c.drawString(50, y_position, f"Date: {entry[1]} | Amount: ${entry[2]:,.2f} | Category: {entry[3]} | Description: {entry[4]}")
        y_position -= 15

    # Expense Table
    y_position -= 30  # Add some space between sections
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y_position, "Expense Entries:")
    y_position -= 20
    c.setFont("Helvetica", 10)
    for entry in expense_entries:
        c.drawString(50, y_position, f"Date: {entry[1]} | Amount: ${entry[2]:,.2f} | Category: {entry[3]} | Description: {entry[4]}")
        y_position -= 15

    # Save PDF
    c.showPage()
    c.save()

    # Return PDF as downloadable file
    pdf_buffer.seek(0)
    return send_file(pdf_buffer, as_attachment=True, download_name="statement.pdf", mimetype="application/pdf")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
