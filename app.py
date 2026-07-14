import os

from dotenv import load_dotenv
from flask import Flask, render_template, session, redirect

from models.database import create_tables, get_connection
from models.levels import get_user_display_level, get_user_play_level
from routes.auth import auth
from routes.test import test
from routes.ai import ai
from routes.profile import profile

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'placement123secret-dev-only')

app.register_blueprint(auth)
app.register_blueprint(test)
app.register_blueprint(ai)
app.register_blueprint(profile)

create_tables()


@app.context_processor
def inject_sidebar_context():
    if 'user_id' not in session:
        return {}
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT target_role FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    return {'target_role': (user['target_role'] or 'Not Set') if user else 'Not Set'}


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT target_role FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) as total FROM attempts WHERE user_id = ?", (session['user_id'],))
    total = cursor.fetchone()

    cursor.execute(
        "SELECT AVG(score * 100.0 / total) as avg FROM attempts WHERE user_id = ?",
        (session['user_id'],),
    )
    avg = cursor.fetchone()

    conn.close()

    stats = {
        'total_tests': total['total'],
        'avg_score'  : round(avg['avg'], 1) if avg['avg'] else 0
    }

    return render_template('dashboard.html',
        username    = session['username'],
        target_role = user['target_role'] or 'Not Set',
        stats       = stats,
        level       = get_user_display_level(session['user_id'])
    )

@app.route('/instructions/aptitude')
def instructions_aptitude():
    if 'user_id' not in session:
        return redirect('/login')
    level_label = get_user_display_level(session['user_id'])
    return render_template('instructions.html',
        icon      = "🧮",
        title     = "Aptitude Test",
        subtitle  = "Test your logical and mathematical skills",
        questions = "10 MCQ",
        time      = "60 seconds",
        passing   = "60%",
        level     = level_label,
        start_url = "/aptitude",
        rules     = [
            "Total 10 multiple choice questions will be asked.",
            "You will get 60 seconds for each question.",
            "Next question will appear automatically when time runs out.",
            "Answer cannot be changed once submitted.",
            "Score 60% or above to unlock Intermediate level.",
            "Use of back button is not allowed.",
        ],
        tips = [
            "Read each question carefully before answering — speed matters but accuracy matters more.",
            "Eliminate obviously wrong options first to improve your chances.",
            "Practice mental math — avoid depending on calculators.",
            "If stuck, skip and come back — don't waste time on one question.",
            "Focus on topics like Percentages, Ratios, Time & Work, and Number Series.",
        ],
        skills_evaluated = [
            "Logical Reasoning", "Quantitative Aptitude", "Data Interpretation",
            "Problem Solving", "Time Management", "Pattern Recognition"
        ]
    )

@app.route('/instructions/interview')
def instructions_interview():
    if 'user_id' not in session:
        return redirect('/login')
        
    level_key = get_user_play_level(session['user_id'])
    level_label = get_user_display_level(session['user_id'])
    
    if level_key == 'beginner':
        q_count = 5
        time_sec = 75
    elif level_key == 'intermediate':
        q_count = 6
        time_sec = 90
    else:
        q_count = 7
        time_sec = 120
        
    return render_template('instructions.html',
        icon      = "💼",
        title     = "HR Interview",
        subtitle  = "Face real role-based HR interview questions",
        questions = f"{q_count} Questions",
        time      = f"{time_sec} sec/question",
        passing   = "60%",
        level     = level_label,
        start_url = "/interview",
        rules     = [
            f"Total {q_count} role-based HR interview questions will be asked based on your level.",
            f"You will get {time_sec} seconds for each question.",
            "You can answer by speaking using your microphone or by manual typing as a fallback.",
            "AI evaluates communication, confidence, professionalism, relevance, and role understanding.",
            "Answers cannot be edited after submission."
        ],
        tips = [
            "Use the STAR method — Situation, Task, Action, Result — for behavioral questions.",
            "Be honest and authentic. Interviewers can sense rehearsed generic answers.",
            "Prepare your 'Tell me about yourself' answer — it's almost always asked first.",
            "Research the role you're targeting. Align your answers to the job requirements.",
            "Maintain a positive tone even when discussing failures or weaknesses.",
        ],
        skills_evaluated = [
            "Communication", "Confidence", "Professionalism",
            "Relevance", "Role Understanding"
        ]
    )

@app.route('/instructions/gd')
def instructions_gd():
    if 'user_id' not in session:
        return redirect('/login')
    level_label = get_user_display_level(session['user_id'])
    return render_template('instructions.html',
        icon      = "🗣️",
        title     = "GD Round",
        subtitle  = "Express your views on a given topic",
        questions = "1 Topic",
        time      = "5 minutes",
        passing   = "60%",
        level     = level_label,
        start_url = "/gd",
        rules     = [
            "You will be given a topic on which you have to write your opinion or speech.",
            "Write minimum 200 words to explain your point of view.",
            "AI will evaluate your clarity, structure and content.",
            "Express your views clearly and confidently.",
            "Answer cannot be edited once submitted.",
        ],
        tips = [
            "Start with a strong opening statement that grabs attention.",
            "Structure your argument: Introduction → Key Points → Conclusion.",
            "Use real-world examples and data to support your viewpoint.",
            "Stay balanced — acknowledge opposing views before countering them.",
            "Conclude with a clear summary. Don't leave your argument hanging.",
        ],
        skills_evaluated = [
            "Clarity of Thought", "Communication", "Argumentation",
            "Structure", "Vocabulary", "Critical Thinking"
        ]
    )

@app.route('/instructions/coding')
def instructions_coding():
    if 'user_id' not in session:
        return redirect('/login')
    level_label = get_user_display_level(session['user_id'])
    return render_template('instructions.html',
        icon      = "💻",
        title     = "Technical Round",
        subtitle  = "Solve technical problems and get AI code review",
        questions = "5 Problems",
        time      = "10 min per problem",
        passing   = "60%",
        level     = level_label,
        start_url = "/coding",
        rules     = [
            "Total 5 coding problems will be given.",
            "You will get 10 minutes for each problem.",
            "Select your preferred language: Python, Java, C++, C, JavaScript or SQL.",
            "Write complete working code in the editor.",
            "AI will review your code and give detailed feedback.",
            "Code cannot be changed once submitted.",
        ],
        tips = [
            "Read the problem statement twice — understand constraints and edge cases.",
            "Start with a brute-force approach, then optimize for time & space complexity.",
            "Write clean, readable code with meaningful variable names.",
            "Test your code with the sample input before submitting.",
            "Handle edge cases: empty input, single element, large numbers, negative values.",
        ],
        skills_evaluated = [
            "DSA Knowledge", "Problem Solving", "Code Quality",
            "Edge Case Handling", "Time Complexity", "Debugging"
        ]
    )

@app.route('/progress')
def progress():
    if 'user_id' not in session:
        return redirect('/login')

    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM attempts
        WHERE user_id = ?
        ORDER BY attempted_at DESC
    """, (session['user_id'],))
    attempts = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) as total FROM attempts WHERE user_id = ?",
                   (session['user_id'],))
    total = cursor.fetchone()

    cursor.execute("SELECT AVG(score * 100.0 / total) as avg FROM attempts WHERE user_id = ?",
                   (session['user_id'],))
    avg = cursor.fetchone()

    cursor.execute("SELECT MAX(score * 100.0 / total) as best FROM attempts WHERE user_id = ?",
                   (session['user_id'],))
    best = cursor.fetchone()

    def get_round_stats(test_type):
        cursor.execute("""
            SELECT COUNT(*) as count, AVG(score * 100.0 / total) as avg
            FROM attempts WHERE user_id = ? AND test_type = ?
        """, (session['user_id'], test_type))
        row = cursor.fetchone()
        return {
            'count': row['count'],
            'avg'  : round(row['avg'], 1) if row['avg'] else 0
        }

    roundwise = {
        'aptitude': get_round_stats('aptitude'),
        'hr'      : get_round_stats('hr_interview'),
        'gd'      : get_round_stats('gd_round'),
        'coding'  : get_round_stats('coding'),
    }

    cursor.execute("SELECT target_role FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()

    stats = {
        'total_tests': total['total'],
        'avg_score'  : round(avg['avg'], 1) if avg['avg'] else 0,
        'best_score' : round(best['best'], 1) if best['best'] else 0,
        'level'      : get_user_display_level(session['user_id'])
    }

    return render_template('progress.html',
        attempts    = attempts,
        stats       = stats,
        roundwise   = roundwise,
        target_role = user['target_role'] or 'Not Set',
    )

if __name__ == '__main__':
    app.run(debug=True)