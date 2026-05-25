# AI Placement System

Flask-based placement prep platform with aptitude, coding, HR interview, GD, and AI-generated career roadmaps (Groq).

## Requirements

- Python 3.11+
- A [Groq](https://console.groq.com/) API key

## Setup

1. Clone or open the project folder.

2. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

3. Copy environment variables:

```bash
copy .env.example .env
```

Edit `.env` and set:

- `GROQ_API_KEY` — your Groq API key
- `FLASK_SECRET_KEY` — a long random string for session security

4. Run the app:

```bash
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) and register an account.

## Features

- **Aptitude & coding** — AI-generated questions with JSON fallback; questions stay in session if you refresh mid-test
- **HR interview** — role-based questions cached per target role
- **Levels** — pass any round at 60%+ to unlock intermediate content
- **Profile** — update your target role at `/profile`

## Project layout

```
app.py              # Main Flask app
routes/             # auth, test, ai, profile
models/             # database + level helpers
templates/          # HTML (Jinja2)
static/css/         # Styles
data/questions.json # Offline question bank
```

## Notes

- SQLite database `database.db` is created automatically on first run.
- Do not commit `.env` or `database.db` (see `.gitignore`).
