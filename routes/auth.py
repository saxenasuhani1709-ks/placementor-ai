from flask import Blueprint, render_template, request, redirect, session
from models.database import get_connection
from models.levels import init_user_levels
from werkzeug.security import generate_password_hash, check_password_hash

auth = Blueprint('auth', __name__)

# ----------------------------------------
# REGISTER
# ----------------------------------------
@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    username    = request.form.get('username', '').strip()
    email       = request.form.get('email', '').strip().lower()
    password    = request.form.get('password', '').strip()
    target_role = request.form.get('target_role', '').strip()

    # Validation
    if not username or not email or not password:
        return render_template('register.html', error="All fields are required!")

    if len(password) < 6:
        return render_template('register.html', error="Password must be at least 6 characters!")

    conn   = get_connection()
    cursor = conn.cursor()

    # Email already exists check
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
    existing = cursor.fetchone()

    if existing:
        conn.close()
        return render_template('register.html', error="This email is already registered! Please login.")

    # Password hash
    hashed_password = generate_password_hash(password)

    # Save to DB
    cursor.execute("""
        INSERT INTO users (username, email, password, target_role)
        VALUES (?, ?, ?, ?)
    """, (username, email, hashed_password, target_role))

    conn.commit()

    # Get new user id
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    new_user = cursor.fetchone()
    conn.close()

    init_user_levels(new_user['id'])

    # Auto login after register
    session['user_id']  = new_user['id']
    session['username'] = username

    return redirect('/dashboard')


# ----------------------------------------
# LOGIN
# ----------------------------------------
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    email    = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '').strip()

    # Validation
    if not email or not password:
        return render_template('login.html', error="All fields are required!")

    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    # User not found
    if not user:
        return render_template('login.html', error="Email not registered! Please register first.")

    # Wrong password
    if not check_password_hash(user['password'], password):
        return render_template('login.html', error="Wrong password! Please try again.")

    # Login success
    session['user_id']  = user['id']
    session['username'] = user['username']

    return redirect('/dashboard')


# ----------------------------------------
# LOGOUT
# ----------------------------------------
@auth.route('/logout')
def logout():
    session.clear()
    return redirect('/login')