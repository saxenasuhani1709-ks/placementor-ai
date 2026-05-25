from flask import Blueprint, render_template, request, session, redirect
from models.database import get_connection
from models.levels import get_user_play_level, maybe_unlock_intermediate
from groq import Groq
from dotenv import load_dotenv
import json
import os
import re

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

test = Blueprint('test', __name__)


def _reuse_session_questions(questions_key, level_key, level_session_key):
    """Reuse cached questions when refreshing mid-test (same level)."""
    questions = session.get(questions_key)
    if questions and session.get(level_session_key) == level_key:
        return questions
    return None


def _load_fallback_questions(q_type, level_key):
    questions_path = os.path.join('data', 'questions.json')
    with open(questions_path, 'r', encoding='utf-8') as f:
        all_questions = json.load(f)
    questions = [
        q for q in all_questions
        if q['type'] == q_type and q['level'] == level_key
    ]
    if not questions and level_key != 'beginner':
        questions = [
            q for q in all_questions
            if q['type'] == q_type and q['level'] == 'beginner'
        ]
    return questions


# ----------------------------------------
# AI QUESTION GENERATOR
# ----------------------------------------
def generate_questions(test_type, level, role, count):

    prompt = f"""
You are an expert placement aptitude test creator.

Generate exactly {count} aptitude questions for placement exam preparation for a {role} role at {level} level.

Rules:
- Questions must be from these topics ONLY:
  Speed & Distance, Profit & Loss, Percentage,
  Number Series, Logical Reasoning, Time & Work,
  Data Interpretation, Coding-Decoding, Ages, Averages
- Difficulty must match {level} level
- Each question must have exactly 4 options
- Only one option must be correct
- Questions must be numerical or logical — NOT general knowledge
- Cover different topics — do not repeat same topic twice
- Questions must be solvable with calculation or logic

Respond in this EXACT JSON format only (no extra text):
[
    {{
        "id": 1,
        "question": "question text here",
        "options": ["option A", "option B", "option C", "option D"],
        "answer": "correct option text here",
        "topic": "topic name"
    }}
]
"""

    try:
        chat = client.chat.completions.create(
            model    = "llama-3.3-70b-versatile",
            messages = [{"role": "user", "content": prompt}]
        )
        response_text = chat.choices[0].message.content
        print("AI QUESTIONS RESPONSE:", response_text[:200])

        # JSON extract karo
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            questions = json.loads(json_match.group())
            return questions
        else:
            raise Exception("JSON not found")

    except Exception as e:
        print("QUESTION GENERATION ERROR:", str(e))
        return None

# ----------------------------------------
# APTITUDE TEST PAGE
# ----------------------------------------
@test.route('/aptitude')
def aptitude():
    if 'user_id' not in session:
        return redirect('/login')

    # User ka role lo
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT target_role FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()

    role      = user['target_role'] if user['target_role'] else 'Software Developer'
    level_key = get_user_play_level(session['user_id'])
    level     = level_key.capitalize()

    questions = _reuse_session_questions('aptitude_questions', level_key, 'aptitude_level')
    if not questions:
        questions = generate_questions('aptitude MCQ', level, role, 10)
    if not questions:
        questions = _load_fallback_questions('aptitude', level_key)

    # Session mein save karo
    session['aptitude_questions'] = questions
    session['aptitude_level']     = level_key

    return render_template('aptitude.html', questions=questions, level=level)

# ----------------------------------------
# SUBMIT APTITUDE
# ----------------------------------------
@test.route('/submit-aptitude', methods=['POST'])
def submit_aptitude():
    if 'user_id' not in session:
        return redirect('/login')

    # Session se questions lo
    questions  = session.get('aptitude_questions', [])
    level_key  = session.get('aptitude_level', get_user_play_level(session['user_id']))

    # Agar session mein nahi hai toh JSON se lo
    if not questions:
        questions = _load_fallback_questions('aptitude', level_key)

    score   = 0
    total   = len(questions)
    results = []

    for q in questions:
        user_answer = request.form.get(f"answer_{q['id']}", "Not Answered")
        correct     = q['answer']
        is_correct  = (user_answer == correct)

        if is_correct:
            score += 1

        results.append({
            'question'   : q['question'],
            'user_answer': user_answer,
            'correct'    : correct,
            'is_correct' : is_correct,
            'topic'      : q.get('topic', 'General')
        })

    percentage = round((score / total) * 100)

    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO attempts (user_id, test_type, level, score, total)
        VALUES (?, ?, ?, ?, ?)
    """, (session['user_id'], 'aptitude', level_key, score, total))

    conn.commit()
    conn.close()

    maybe_unlock_intermediate(session['user_id'], percentage)

    # Session clear karo
    session.pop('aptitude_questions', None)
    session.pop('aptitude_level', None)

    return render_template('result.html',
        score      = score,
        total      = total,
        percentage = percentage,
        results    = results
    )

# ----------------------------------------
# CODING TEST PAGE
# ----------------------------------------
@test.route('/coding')
def coding():
    if 'user_id' not in session:
        return redirect('/login')

    # User role
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT target_role FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()

    role      = user['target_role'] if user['target_role'] else 'Software Developer'
    level_key = get_user_play_level(session['user_id'])
    level     = level_key.capitalize()

    questions = _reuse_session_questions('coding_questions', level_key, 'coding_level')
    if questions:
        return render_template('coding.html', questions=questions, level=level)

    # AI coding questions generate
    prompt = f"""
You are an expert coding interviewer.

Generate exactly 5 {level_key} level coding problems for a fresher applying for {role} role.

Rules:
- Problems must match {level_key} difficulty
- Each problem must have a clear example input and output
- Include a helpful hint
- Problems must be relevant to {role} role

Respond in this EXACT JSON format only (no extra text):
[
    {{
        "id": 1,
        "question": "problem description here with example",
        "example_input": "input here",
        "example_output": "output here",
        "topic": "topic name",
        "hint": "helpful hint here"
    }}
]
"""

    try:
        chat = client.chat.completions.create(
            model    = "llama-3.3-70b-versatile",
            messages = [{"role": "user", "content": prompt}]
        )
        response_text = chat.choices[0].message.content
        json_match    = re.search(r'\[.*\]', response_text, re.DOTALL)

        if json_match:
            questions = json.loads(json_match.group())
        else:
            raise Exception("JSON not found")

    except Exception as e:
        print("CODING QUESTION ERROR:", str(e))
        questions = _load_fallback_questions('coding', level_key)

    session['coding_questions'] = questions
    session['coding_level']       = level_key
    return render_template('coding.html', questions=questions, level=level)

# ----------------------------------------
# SUBMIT CODING
# ----------------------------------------
@test.route('/submit-coding', methods=['POST'])
def submit_coding():
    if 'user_id' not in session:
        return redirect('/login')

    questions = session.get('coding_questions', [])
    level_key = session.get('coding_level', get_user_play_level(session['user_id']))

    if not questions:
        questions = _load_fallback_questions('coding', level_key)

    results     = []
    total_score = 0

    for q in questions:
        code     = request.form.get(f"code_{q['id']}", "No code written")
        language = request.form.get(f"lang_{q['id']}", "python")

        prompt = f"""
You are an expert coding interviewer evaluating a fresher candidate.

Problem: {q['question']}
Expected Output for input {q['example_input']}: {q['example_output']}
Candidate's Code ({language}):
{code}

Evaluate the code and respond in this EXACT format only:
Score: [number from 1 to 10]
Correct_Approach: [is the logic correct? explain briefly]
Issues: [any bugs, errors, or missing edge cases]
Better_Approach: [suggest a better or optimal solution briefly]
"""

        try:
            chat = client.chat.completions.create(
                model    = "llama-3.3-70b-versatile",
                messages = [{"role": "user", "content": prompt}]
            )
            feedback_text = chat.choices[0].message.content

        except Exception as e:
            print("CODING API ERROR:", str(e))
            feedback_text = ""

        score            = 5
        correct_approach = "N/A"
        issues           = "N/A"
        better_approach  = "N/A"

        if feedback_text:
            for line in feedback_text.strip().split('\n'):
                line = line.strip()
                if line.lower().startswith("score:"):
                    try:
                        numbers = re.findall(r'\d+', line)
                        if numbers:
                            score = min(int(numbers[0]), 10)
                    except:
                        score = 5
                elif line.lower().startswith("correct_approach:"):
                    correct_approach = line.split(":", 1)[1].strip()
                elif line.lower().startswith("issues:"):
                    issues = line.split(":", 1)[1].strip()
                elif line.lower().startswith("better_approach:"):
                    better_approach = line.split(":", 1)[1].strip()

        total_score += score

        results.append({
            'question'        : q['question'],
            'code'            : code,
            'language'        : language,
            'score'           : score,
            'correct_approach': correct_approach,
            'issues'          : issues,
            'better_approach' : better_approach
        })

    correct    = sum(1 for r in results if r['score'] >= 6)
    percentage = round((correct / len(questions)) * 100)

    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO attempts (user_id, test_type, level, score, total)
        VALUES (?, ?, ?, ?, ?)
    """, (session['user_id'], 'coding', level_key, correct, len(questions)))
    conn.commit()
    conn.close()

    maybe_unlock_intermediate(session['user_id'], percentage)

    session.pop('coding_questions', None)
    session.pop('coding_level', None)

    return render_template('coding_result.html',
        results    = results,
        correct    = correct,
        total      = len(questions),
        percentage = percentage
    )