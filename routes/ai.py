from flask import Blueprint, render_template, request, session, redirect
from models.database import get_connection
from models.levels import get_user_play_level, maybe_unlock_intermediate
from groq import Groq
from dotenv import load_dotenv
import json
import os
import re
import random

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
client  = Groq(api_key=api_key)

ai = Blueprint('ai', __name__)

# ----------------------------------------
# HR INTERVIEW QUESTIONS
# ----------------------------------------
HR_QUESTIONS = [
    "Tell me about yourself.",
    "What are your strengths and weaknesses?",
    "Why do you want to join our company?",
    "Where do you see yourself in 5 years?",
    "How do you handle pressure and tight deadlines?"
]

GD_TOPICS_BEGINNER = [
    "Online learning vs classroom learning",
    "Social media impact on students",
    "Is coding necessary for everyone?",
    "Should students use AI tools for learning?",
    "Books vs E-books: Which is better?",
    "Is peer pressure always bad?",
    "Importance of sports in student life.",
    "Do grades define a student's intelligence?",
    "Is technology making us lazier?",
    "Should school uniforms be mandatory?",
    "Impact of video games on youth.",
    "City life vs Village life.",
    "Importance of learning English in today's world.",
    "Is homework really necessary?",
    "Should mobile phones be allowed in schools?"
]

GD_TOPICS_INTERMEDIATE = [
    "You are leading a team where members are not contributing. What will you do?",
    "Your project team is missing deadlines. How would you handle it?",
    "A teammate is not cooperating during an important assignment.",
    "You found out a colleague is taking credit for your work.",
    "You have to choose between a high-paying job you hate or a low-paying job you love.",
    "Your manager gives you a task with an impossible deadline.",
    "You disagree with your team leader's decision. How do you approach it?",
    "A client is unhappy with your team's deliverable despite meeting all requirements.",
    "You notice a serious flaw in a project right before the final presentation.",
    "Your team is split 50/50 on a critical decision.",
    "How would you handle a situation where you made a major mistake at work?",
    "You are assigned to work with someone you strongly dislike.",
    "Your project budget is suddenly cut by half.",
    "You have to deliver bad news to a client.",
    "You are asked to do a task outside your job description."
]

GD_TOPICS_ADVANCED = [
    "A company wants to replace employees with AI to reduce costs. Discuss.",
    "Is remote work sustainable in the long term?",
    "Startup culture vs job security",
    "Impact of automation on employment",
    "Should companies prioritize profit over environmental sustainability?",
    "The 4-day workweek: Is it practical for all industries?",
    "Data privacy vs National security.",
    "Is the gig economy exploiting workers?",
    "Impact of global economic recession on IT jobs.",
    "Should the government regulate artificial intelligence?",
    "Cryptocurrency: Future of finance or a speculative bubble?",
    "The role of corporate social responsibility (CSR).",
    "Is the current education system preparing students for the future?",
    "Ethics of targeted advertising using user data.",
    "Will globalization survive in the post-pandemic world?"
]

def _get_hr_questions(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT target_role FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    role = user['target_role'] if user and user['target_role'] else 'Software Developer'
    level_key = get_user_play_level(user_id)

    cached = session.get('hr_questions')
    if cached and session.get('hr_questions_role') == role and session.get('hr_questions_level') == level_key:
        return cached

    if level_key == 'beginner':
        structure = "2 General HR, 2 Role-Based, 1 Behavioral"
        count = 5
    elif level_key == 'intermediate':
        structure = "2 General HR, 2 Role-Based, 2 Behavioral"
        count = 6
    else:
        structure = "1 General HR, 3 Role-Based, 3 Behavioral/Situational"
        count = 7

    prompt = f"""
Generate exactly {count} HR interview questions for a fresher applying for a {role} role.

Rules:
- Questions must be realistic and placement-oriented.
- Structure must exactly match: {structure}
- Each item is a single question string.

Respond in this EXACT JSON format only (no extra text):
["question 1", "question 2", ...]
"""

    try:
        chat = client.chat.completions.create(
            model    = "llama-3.3-70b-versatile",
            messages = [{"role": "user", "content": prompt}],
        )
        response_text = chat.choices[0].message.content
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            questions = json.loads(json_match.group())
            if isinstance(questions, list) and len(questions) >= count:
                questions = [str(q) for q in questions[:count]]
                session['hr_questions'] = questions
                session['hr_questions_role'] = role
                session['hr_questions_level'] = level_key
                return questions
    except Exception as e:
        print("HR QUESTION GENERATION ERROR:", str(e))

    session['hr_questions'] = HR_QUESTIONS[:count]
    session['hr_questions_role'] = role
    session['hr_questions_level'] = level_key
    return HR_QUESTIONS[:count]

@ai.route('/api/hr-followup', methods=['POST'])
def hr_followup():
    if 'user_id' not in session:
        return jsonify({'followup': None})
        
    data = request.json
    role = session.get('hr_questions_role', 'Software Developer')
    question = data.get('question')
    answer = data.get('answer')
    
    prompt = f"""
You are an HR interviewer interviewing a fresher for a {role} role.
You asked: "{question}"
Candidate answered: "{answer}"

If the answer is extremely short, weak, or unclear, generate 1 highly relevant follow-up question.
If the answer is strong, you can ask 1 advanced follow-up question.
However, if the answer is completely satisfactory and no follow-up is truly needed, respond with EXACTLY "SKIP".

Keep the follow-up question short and realistic.
Respond with ONLY the question text or "SKIP".
"""
    try:
        chat = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        res = chat.choices[0].message.content.strip()
        if res == "SKIP" or res.lower().startswith("skip") or len(res) < 5:
            return jsonify({'followup': None})
        else:
            return jsonify({'followup': res})
    except:
        return jsonify({'followup': None})

# ----------------------------------------
# INTERVIEW PAGE
# ----------------------------------------
@ai.route('/interview')
def interview():
    if 'user_id' not in session:
        return redirect('/login')
    questions = _get_hr_questions(session['user_id'])
    level_key = get_user_play_level(session['user_id'])
    time_limit = 75 if level_key == 'beginner' else 90 if level_key == 'intermediate' else 120
    
    return render_template('interview.html', questions=questions, time_limit=time_limit, role=session.get('hr_questions_role', 'Software Developer'))

# ----------------------------------------
# SUBMIT INTERVIEW
# ----------------------------------------
@ai.route('/submit-interview', methods=['POST'])
def submit_interview():
    if 'user_id' not in session:
        return redirect('/login')

    interview_data_str = request.form.get('interview_data', '[]')
    try:
        interview_data = json.loads(interview_data_str)
    except:
        interview_data = []

    role = session.get('hr_questions_role', 'Software Developer')
    
    transcript_text = ""
    for idx, qa in enumerate(interview_data):
        transcript_text += f"\nQ{idx+1}: {qa.get('question')}\nAnswer: {qa.get('answer')}\n"
        if qa.get('follow_up_question') and qa.get('follow_up_answer'):
            transcript_text += f"Follow-up: {qa.get('follow_up_question')}\nFollow-up Answer: {qa.get('follow_up_answer')}\n"

    prompt = f"""
You are a strict HR interviewer evaluating a fresher candidate for a {role} role.

Interview Transcript:
{transcript_text}

Evaluate the candidate deeply on the following parameters (1-10):
- Communication: Grammar, clarity, sentence formation.
- Confidence: Tone, assertiveness.
- Professionalism: Interview etiquette, appropriateness.
- Relevance: Sticking to the point, answering what was asked.
- Role Understanding: Knowledge of {role} expectations.
- Behavioral Skills: Problem-solving, teamwork, adaptability.
- Suggestion: One highly actionable tip to improve.

Respond in this EXACT format only, each on a new line (no extra text):
Communication: [number from 1 to 10]
Confidence: [number from 1 to 10]
Professionalism: [number from 1 to 10]
Relevance: [number from 1 to 10]
Role Understanding: [number from 1 to 10]
Behavioral: [number from 1 to 10]
Suggestion: [1-2 sentences of specific actionable advice]
"""

    try:
        chat = client.chat.completions.create(
            model = "llama-3.3-70b-versatile",
            messages = [{"role": "user", "content": prompt}]
        )
        feedback_text = chat.choices[0].message.content
        print("HR AI RESPONSE:", feedback_text)

    except Exception as e:
        print("HR API ERROR:", str(e))
        feedback_text = ""

    feedback = {
        'communication': 5, 'confidence': 5, 'professionalism': 5,
        'relevance': 5, 'role_understanding': 5, 'behavioral': 5,
        'suggestion': 'Try to be more confident and clear.'
    }

    if feedback_text:
        for line in feedback_text.strip().split('\n'):
            line = line.strip()
            if line.lower().startswith("communication:"):
                try: feedback['communication'] = min(int(re.findall(r'\d+', line)[0]), 10)
                except: pass
            elif line.lower().startswith("confidence:"):
                try: feedback['confidence'] = min(int(re.findall(r'\d+', line)[0]), 10)
                except: pass
            elif line.lower().startswith("professionalism:"):
                try: feedback['professionalism'] = min(int(re.findall(r'\d+', line)[0]), 10)
                except: pass
            elif line.lower().startswith("relevance:"):
                try: feedback['relevance'] = min(int(re.findall(r'\d+', line)[0]), 10)
                except: pass
            elif line.lower().startswith("role understanding:"):
                try: feedback['role_understanding'] = min(int(re.findall(r'\d+', line)[0]), 10)
                except: pass
            elif line.lower().startswith("behavioral:"):
                try: feedback['behavioral'] = min(int(re.findall(r'\d+', line)[0]), 10)
                except: pass
            elif line.lower().startswith("suggestion:"):
                feedback['suggestion'] = line.split(":", 1)[1].strip()

    total_score = feedback['communication'] + feedback['confidence'] + feedback['professionalism'] + \
                  feedback['relevance'] + feedback['role_understanding'] + feedback['behavioral']
    
    avg_score  = round(total_score / 6)
    percentage = round((avg_score / 10) * 100)
    level_key  = get_user_play_level(session['user_id'])

    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO attempts (user_id, test_type, level, score, total, feedback)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session['user_id'], 'hr_interview', level_key, avg_score, 10, str(feedback)))
    conn.commit()
    conn.close()

    maybe_unlock_intermediate(session['user_id'], percentage)

    session.pop('hr_questions', None)
    session.pop('hr_questions_role', None)
    session.pop('hr_questions_level', None)

    return render_template('ai_result.html',
        interview_data = interview_data,
        feedback   = feedback,
        avg_score  = avg_score,
        percentage = percentage
    )

# ----------------------------------------
# GD ROUND PAGE
# ----------------------------------------
@ai.route('/gd')
def gd():
    if 'user_id' not in session:
        return redirect('/login')

    level_key = get_user_play_level(session['user_id'])
    
    if level_key == 'beginner':
        topic = random.choice(GD_TOPICS_BEGINNER)
        gd_time = 120
    elif level_key == 'intermediate':
        topic = random.choice(GD_TOPICS_INTERMEDIATE)
        gd_time = 180
    else: # advanced
        topic = random.choice(GD_TOPICS_ADVANCED)
        gd_time = 240

    return render_template('gd.html', topic=topic, gd_time=gd_time, is_followup=False, history="[]", followups_asked=0)

# ----------------------------------------
# SUBMIT GD
# ----------------------------------------
@ai.route('/submit-gd', methods=['POST'])
def submit_gd():
    if 'user_id' not in session:
        return redirect('/login')

    topic = request.form.get('topic')
    answer = request.form.get('answer', '')
    gd_time = request.form.get('gd_time', '120')
    followups_asked = int(request.form.get('followups_asked', 0))
    history_str = request.form.get('history', '[]')
    
    import json
    try:
        history = json.loads(history_str)
    except:
        history = []

    if followups_asked == 0:
        history.append({"role": "user", "content": f"Initial Answer: {answer}"})
    else:
        history.append({"role": "user", "content": f"Follow-up Answer: {answer}"})

    if followups_asked < 1:
        # Generate follow-up question
        history_text = "\n".join([f"{item['role']}: {item['content']}" for item in history])
        prompt = f"""
You are conducting a Group Discussion round.
Topic: {topic}
Conversation so far:
{history_text}

Generate ONE highly relevant follow-up question based on the user's initial answer.
- If response is weak/short: Ask them to clarify or expand.
- If response is average: Ask for a real-life example.
- If response is strong: Ask for an alternative perspective or edge case.
Respond with ONLY the question text (no extra text, no quotes).
"""
        try:
            chat = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            followup_q = chat.choices[0].message.content.strip()
        except:
            followup_q = "Could you elaborate more on your points with an example?"

        history.append({"role": "interviewer", "content": followup_q})
        return render_template('gd.html', 
            topic=topic, 
            gd_time=120, 
            is_followup=True, 
            followup_question=followup_q,
            history=json.dumps(history),
            followups_asked=followups_asked + 1
        )

    # Final Evaluation
    history_text = "\n".join([f"{item['role']}: {item['content']}" for item in history])
    prompt = f"""
You are a strict and detailed evaluator for a Group Discussion round in a campus placement interview.

Topic: {topic}

Candidate's Complete Interaction:
{history_text}

Evaluate the response deeply on the following parameters:
- Communication: Grammar, vocabulary, and sentence formation.
- Clarity of thoughts: Structure, coherence, and flow of ideas.
- Confidence: Tone, assertiveness, and persuasion.
- Topic relevance: Sticking to the core topic, examples, and knowledge depth.
- Analytical thinking: Problem-solving approach, reasoning, and depth of argument.
- Suggestions: One or two highly actionable tips.

Respond in this EXACT format only, each on a new line (no extra text):
Communication: [number from 1 to 10]
Clarity: [number from 1 to 10]
Confidence: [number from 1 to 10]
Relevance: [number from 1 to 10]
Analytical: [number from 1 to 10]
Suggestion: [1-2 sentences of specific actionable advice]
"""

    try:
        chat = client.chat.completions.create(
            model = "llama-3.3-70b-versatile",
            messages = [{"role": "user", "content": prompt}]
        )
        feedback_text = chat.choices[0].message.content
        print("GD AI RESPONSE:", feedback_text)

    except Exception as e:
        print("GD API ERROR:", str(e))
        feedback_text = ""

    # Parse feedback
    comm_score    = 5
    clarity_score = 5
    conf_score    = 5
    rel_score     = 5
    analytical_score = 5
    suggestion    = "N/A"

    if feedback_text:
        for line in feedback_text.strip().split('\n'):
            line = line.strip()
            if line.lower().startswith("communication:"):
                try: comm_score = min(int(re.findall(r'\d+', line)[0]), 10)
                except: pass
            elif line.lower().startswith("clarity:"):
                try: clarity_score = min(int(re.findall(r'\d+', line)[0]), 10)
                except: pass
            elif line.lower().startswith("confidence:"):
                try: conf_score = min(int(re.findall(r'\d+', line)[0]), 10)
                except: pass
            elif line.lower().startswith("relevance:"):
                try: rel_score = min(int(re.findall(r'\d+', line)[0]), 10)
                except: pass
            elif line.lower().startswith("analytical:"):
                try: analytical_score = min(int(re.findall(r'\d+', line)[0]), 10)
                except: pass
            elif line.lower().startswith("suggestion:"):
                suggestion = line.split(":", 1)[1].strip()

    total_score = comm_score + clarity_score + conf_score + rel_score + analytical_score
    score       = round(total_score / 5)
    percentage  = round((score / 10) * 100)
    level_key   = get_user_play_level(session['user_id'])

    feedback = {
        'communication': comm_score,
        'clarity': clarity_score,
        'confidence': conf_score,
        'relevance': rel_score,
        'analytical': analytical_score,
        'suggestion': suggestion
    }

    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO attempts (user_id, test_type, level, score, total, feedback)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session['user_id'], 'gd_round', level_key, score, 10, str(feedback)))
    conn.commit()
    conn.close()

    maybe_unlock_intermediate(session['user_id'], percentage)

    return render_template('gd_result.html',
        topic      = topic,
        history    = history,
        score      = score,
        percentage = percentage,
        feedback   = feedback
    )
# ----------------------------------------
# ROADMAP PAGE - GET
# ----------------------------------------
@ai.route('/roadmap', methods=['GET'])
def roadmap():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('roadmap.html')