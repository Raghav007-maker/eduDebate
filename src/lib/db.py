import sqlite3
import os

DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
DB_FILE = os.path.join(DB_DIR, "edudebate.db")

def init_db() -> None:
    """Initializes the SQLite database and creates the debates table if it does not exist."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS debates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                research_output TEXT,
                advocate_output TEXT,
                factcheck_output TEXT,
                synthesis_output TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()

def save_debate(
    question: str,
    research_output: str,
    advocate_output: str,
    factcheck_output: str,
    synthesis_output: str
) -> int:
    """Saves a debate session run and returns its unique row ID."""
    init_db()
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO debates (
                question, research_output, advocate_output, factcheck_output, synthesis_output
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (question, research_output, advocate_output, factcheck_output, synthesis_output)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def get_past_debates() -> list[dict]:
    """Retrieves all past debate sessions from the database, ordered by latest first."""
    init_db()
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, question, research_output, advocate_output, factcheck_output, synthesis_output, timestamp FROM debates ORDER BY timestamp DESC"
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
