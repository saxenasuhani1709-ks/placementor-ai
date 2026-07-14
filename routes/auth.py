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
        return render_template('index.html', show_modal='register')

    username    = request.form.get('username', '').strip()
    email       = request.form.get('email', '').strip().lower()
    password    = request.form.get('password', '').strip()
    target_role = request.form.get('target_role', '').strip()

    # Validation
    if not username or not email or not password:
        return render_template('index.html', error="All fields are required!", show_modal='register')

    if len(password) < 6:
        return render_template('index.html', error="Password must be at least 6 characters!", show_modal='register')

    conn   = get_connection()
    cursor = conn.cursor()

    # Email already exists check
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
    existing = cursor.fetchone()

    if existing:
        conn.close()
        return render_template('index.html', error="This email is already registered! Please login.", show_modal='register')

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
        return render_template('index.html', show_modal='login')

    email    = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '').strip()

    # Validation
    if not email or not password:
        return render_template('index.html', error="All fields are required!", show_modal='login')

    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    # User not found
    if not user:
        return render_template('index.html', error="Email not registered! Please register first.", show_modal='login')

    # Wrong password
    if not check_password_hash(user['password'], password):
        return render_template('index.html', error="Wrong password! Please try again.", show_modal='login')

    # Login success
    session['user_id']  = user['id']
    session['username'] = user['username']

    return redirect('/dashboard')


# ----------------------------------------
# RESET PASSWORD
# ----------------------------------------
@auth.route('/reset-password', methods=['POST'])
def reset_password():
    email        = request.form.get('email', '').strip().lower()
    new_password = request.form.get('password', '').strip()

    if not email or not new_password:
        return render_template('index.html', error="All fields are required!", show_modal='forgot')

    if len(new_password) < 6:
        return render_template('index.html', error="Password must be at least 6 characters!", show_modal='forgot')

    conn   = get_connection()
    cursor = conn.cursor()

    # Check user exists
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return render_template('index.html', error="Email address not found in system!", show_modal='forgot')

    # Hash new password and update
    hashed_password = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_password, user['id']))
    conn.commit()
    conn.close()

    return render_template('index.html', success="Password reset successfully! Please sign in.", show_modal='login')


# ----------------------------------------
# LOGOUT
# ----------------------------------------
@auth.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

