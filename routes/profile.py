from flask import Blueprint, render_template, request, session, redirect
from models.database import get_connection
from models.levels import get_user_display_level

profile = Blueprint('profile', __name__)

TARGET_ROLES = [
    'Software Developer',
    'Data Analyst',
    'Web Developer',
    'DevOps Engineer',
    'AI/ML Engineer',
]


def _clear_test_sessions():
    for key in (
        'aptitude_questions', 'aptitude_level',
        'coding_questions', 'coding_level',
        'hr_questions', 'hr_questions_role',
    ):
        session.pop(key, None)


@profile.route('/profile', methods=['GET', 'POST'])
def user_profile():
    if 'user_id' not in session:
        return redirect('/login')

    conn   = get_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        target_role = request.form.get('target_role', '').strip()
        if target_role not in TARGET_ROLES:
            target_role = ''

        cursor.execute(
            "UPDATE users SET target_role = ? WHERE id = ?",
            (target_role, session['user_id']),
        )
        conn.commit()
        _clear_test_sessions()
        success = True
    else:
        success = False

    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()

    cursor.execute(
        "SELECT COUNT(*) as total FROM attempts WHERE user_id = ?",
        (session['user_id'],),
    )
    total_attempts = cursor.fetchone()['total']

    cursor.execute(
        "SELECT AVG(score * 100.0 / total) as avg FROM attempts WHERE user_id = ?",
        (session['user_id'],),
    )
    avg_row = cursor.fetchone()

    conn.close()

    stats = {
        'total_tests': total_attempts,
        'avg_score'  : round(avg_row['avg'], 1) if avg_row['avg'] else 0,
        'level'      : get_user_display_level(session['user_id']),
    }

    return render_template(
        'profile.html',
        user        = user,
        stats       = stats,
        roles       = TARGET_ROLES,
        success     = success,
        active      = 'profile',
        target_role = user['target_role'] or 'Not Set',
    )
