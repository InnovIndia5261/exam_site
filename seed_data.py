# seed_data.py
import csv
from pathlib import Path
from db import DB
from auth import hash_password

ROOT = Path(__file__).parent

def seed_users(db: DB, csv_path: Path):
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        cnt = 0
        for row in reader:
            username = row['username'].strip()
            full_name = row['full_name'].strip()
            pwd = row.get('password', '').strip()
            pwd_hash = hash_password(pwd) if pwd else None
            db.execute(
                "INSERT OR IGNORE INTO users(username, full_name, password_hash, role) VALUES (?,?,?,?)",
                (username, full_name, pwd_hash, 'student')
            )
            cnt += 1
    print(f"Seeded users: {cnt}")
    if not db.fetch_one("SELECT 1 FROM users WHERE username='admin'", ()):
        db.execute(
            "INSERT INTO users(username, full_name, password_hash, role) VALUES (?,?,?,?)",
            ("admin", "Administrator", hash_password("admin123"), "admin")
        )

def seed_questions(db: DB, csv_path: Path):
    def safe_int(x, default=None):
        try:
            return int(x)
        except Exception:
            return default

    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        cnt = 0
        for row in reader:
            qtype = (row.get('qtype') or '').strip().lower()
            prompt = row.get('prompt')
            options_json = row.get('options_json')
            answer = row.get('answer')
            topic = row.get('topic')
            difficulty = (row.get('difficulty') or 'medium').strip().lower()
            marks = safe_int(row.get('marks'), 1)  # NEW

            language_id = None
            tests_json = None
            if qtype == 'code':
                language_id = safe_int(row.get('language_id'))
                tests_json = row.get('tests_json')

            db.execute(
                "INSERT INTO questions(qtype, prompt, options_json, answer, topic, difficulty, marks, language_id, tests_json) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (qtype, prompt, options_json, answer, topic, difficulty, marks, language_id, tests_json)
            )
            cnt += 1
    print(f"Seeded questions: {cnt}")

if __name__ == "__main__":
    db = DB()
    db.run_script(ROOT / 'schema.sql')
    seed_users(db, ROOT / 'data' / 'users.csv')
    seed_questions(db, ROOT / 'data' / 'questions.csv')
    print("Seed complete.")
