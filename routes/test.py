from flask import Blueprint, render_template, request, session, redirect, jsonify
from models.database import get_connection
from models.levels import get_user_play_level, maybe_unlock_intermediate
from groq import Groq
from dotenv import load_dotenv
import json
import os
import re
import subprocess
import sys

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
    )# ----------------------------------------
# CODE EXECUTION HELPERS
# ----------------------------------------
def _run_code_internal(code, language, stdin_data):
    if language == 'python':
        try:
            res = subprocess.run(
                [sys.executable, "-c", code],
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=4
            )
            return {
                "status": "success" if res.returncode == 0 else "error",
                "stdout": res.stdout,
                "stderr": res.stderr
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "stdout": "", "stderr": "Time Limit Exceeded (4s)"}
        except Exception as e:
            return {"status": "error", "stdout": "", "stderr": str(e)}
    else:
        # Simulate compilation and output via Groq AI
        prompt = f"""
You are a sandboxed compiler and code execution engine.
Compile and run the following code with the provided standard input (stdin) and capture the stdout/stderr.

Language: {language}
Input (stdin):
{stdin_data}

Code:
{code}

Respond in this exact JSON format only (no markdown, no extra text):
{{
    "status": "success" or "error",
    "stdout": "output printed to standard output",
    "stderr": "syntax errors, compilation errors, or runtime exceptions if any"
}}
"""
        try:
            chat = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            res = json.loads(chat.choices[0].message.content)
            return {
                "status": res.get("status", "success"),
                "stdout": res.get("stdout", ""),
                "stderr": res.get("stderr", "")
            }
        except Exception as e:
            return {"status": "error", "stdout": "", "stderr": f"Execution/Simulation failed: {str(e)}"}


# ----------------------------------------
# RUN CODE API ENDPOINT
# ----------------------------------------
@test.route('/api/run-code', methods=['POST'])
def api_run_code():
    if 'user_id' not in session:
        return jsonify({"status": "error", "stderr": "Session expired. Please log in again."}), 401
    
    data = request.json or {}
    code = data.get("code", "")
    language = data.get("language", "python").lower()
    stdin_data = data.get("stdin", "")
    
    result = _run_code_internal(code, language, stdin_data)
    return jsonify(result)


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

    # AI coding questions generate with placement-level DSA constraints
    prompt = f"""
You are an expert DSA coding interviewer.

Generate exactly 3 placement-level Data Structures & Algorithms (DSA) problems for a candidate applying for {role} role at {level_key} level.

Rules:
- Problems must match {level_key} level (Beginner: Array/String basics; Intermediate: Sorting, Two Pointers, Stacks, HashMaps; Advanced: DP, Trees, Graphs, Greedy).
- Problems must expect code to read input from standard input (stdin) and print output to standard output (stdout).
- Include clear HackerRank-style problem description, example input, example output, and helpful hint.
- Include exactly 3 hidden test cases per problem.
- DO NOT INCLUDE ANY MARKDOWN formatting (like ```json), JUST THE RAW JSON ARRAY.

Respond in this EXACT JSON format only:
[
    {{
        "id": 1,
        "question": "problem description here",
        "example_input": "1 2",
        "example_output": "3",
        "topic": "topic name",
        "hint": "helpful hint",
        "test_cases": [
            {{"input": "1 2", "expected_output": "3"}},
            {{"input": "-5 10", "expected_output": "5"}},
            {{"input": "0 0", "expected_output": "0"}}
        ]
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
    correct     = 0

    for q in questions:
        code     = request.form.get(f"code_{q['id']}", "No code written").strip()
        language = request.form.get(f"lang_{q['id']}", "python").lower()

        # Run hidden test cases
        test_cases = q.get('test_cases', [])
        if not test_cases:
            test_cases = [{"input": q['example_input'], "expected_output": q['example_output']}]

        passed_cases = 0
        total_cases = len(test_cases)
        tc_results = []

        for idx, tc in enumerate(test_cases):
            tc_input = tc.get('input', '')
            tc_expected = tc.get('expected_output', '').strip()

            run_res = _run_code_internal(code, language, tc_input)
            tc_output = run_res.get('stdout', '').strip()
            tc_error = run_res.get('stderr', '').strip()

            is_passed = (tc_output == tc_expected)
            if is_passed:
                passed_cases += 1

            tc_results.append({
                "id": idx + 1,
                "input": tc_input,
                "expected": tc_expected,
                "actual": tc_output,
                "error": tc_error,
                "passed": is_passed
            })

        # Score is based on test case correctness (scale 1 to 10)
        score = round((passed_cases / total_cases) * 10) if total_cases > 0 else 0
        if score >= 6:
            correct += 1

        # Use AI to provide feedback on correctness and optimal approach
        feedback_prompt = f"""
You are an expert coding interviewer evaluating a fresher candidate.

Problem: {q['question']}
Candidate's Code ({language}):
{code}

Test Case Results: Passed {passed_cases} out of {total_cases} test cases.

Evaluate the code and respond in this EXACT format only:
Correct_Approach: [Is the logic correct? explain briefly]
Issues: [Mention bugs, inefficiencies, or missing edge cases]
Better_Approach: [suggest a better or optimal solution briefly]
"""
        correct_approach = "N/A"
        issues           = "N/A"
        better_approach  = "N/A"

        try:
            chat = client.chat.completions.create(
                model    = "llama-3.3-70b-versatile",
                messages = [{"role": "user", "content": feedback_prompt}]
            )
            feedback_text = chat.choices[0].message.content
            
            for line in feedback_text.strip().split('\n'):
                line = line.strip()
                if line.lower().startswith("correct_approach:"):
                    correct_approach = line.split(":", 1)[1].strip()
                elif line.lower().startswith("issues:"):
                    issues = line.split(":", 1)[1].strip()
                elif line.lower().startswith("better_approach:"):
                    better_approach = line.split(":", 1)[1].strip()

        except Exception as e:
            print("CODING API ERROR:", str(e))

        results.append({
            'question'        : q['question'],
            'code'            : code,
            'language'        : language,
            'score'           : score,
            'passed_cases'    : passed_cases,
            'total_cases'     : total_cases,
            'tc_results'      : tc_results,
            'correct_approach': correct_approach,
            'issues'          : issues,
            'better_approach' : better_approach
        })

    percentage = round((correct / len(questions)) * 100) if questions else 0

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