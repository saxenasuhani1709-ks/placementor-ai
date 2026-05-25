"""Shared level progression helpers (beginner -> intermediate)."""

from models.database import get_connection

LEVEL_ORDER = {
    'beginner': 0,
    'intermediate': 1,
}

PASS_PERCENTAGE = 60


def ensure_user_levels(user_id):
    """Ensure existing users have at least beginner unlocked."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM levels WHERE user_id = ? AND level_name = 'beginner'",
        (user_id,),
    )
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO levels (user_id, level_name, unlocked) VALUES (?, 'beginner', 1)",
            (user_id,),
        )
        conn.commit()
    conn.close()


def init_user_levels(user_id):
    """Create default beginner level for a new user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO levels (user_id, level_name, unlocked) VALUES (?, 'beginner', 1)",
        (user_id,),
    )
    conn.commit()
    conn.close()


def get_user_play_level(user_id):
    """Highest unlocked level used for tests (beginner or intermediate)."""
    ensure_user_levels(user_id)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT level_name FROM levels WHERE user_id = ? AND unlocked = 1",
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    best = 'beginner'
    for row in rows:
        name = row['level_name'].lower()
        if LEVEL_ORDER.get(name, -1) > LEVEL_ORDER.get(best, -1):
            best = name
    return best


def get_user_display_level(user_id):
    return get_user_play_level(user_id).capitalize()


def maybe_unlock_intermediate(user_id, percentage):
    """Unlock intermediate when the user passes (>= 60%)."""
    if percentage < PASS_PERCENTAGE:
        return

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM levels WHERE user_id = ? AND level_name = 'intermediate'",
        (user_id,),
    )
    existing = cursor.fetchone()

    if not existing:
        cursor.execute(
            "INSERT INTO levels (user_id, level_name, unlocked) VALUES (?, 'intermediate', 1)",
            (user_id,),
        )
    else:
        cursor.execute(
            "UPDATE levels SET unlocked = 1 WHERE user_id = ? AND level_name = 'intermediate'",
            (user_id,),
        )

    conn.commit()
    conn.close()
