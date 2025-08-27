# auth.py
import os, base64, hashlib, hmac
from typing import Optional

_ITER = 200_000
_SALT_LEN = 16
_DK_LEN = 32

def _pbkdf2(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITER, _DK_LEN)

def hash_password(plain: str) -> str:
    salt = os.urandom(_SALT_LEN)
    dk = _pbkdf2(plain, salt)
    return base64.b64encode(salt + dk).decode("utf-8")

def check_password(plain: str, stored: str) -> bool:
    try:
        raw = base64.b64decode(stored.encode("utf-8"))
        salt, dk = raw[:_SALT_LEN], raw[_SALT_LEN:]
        test = _pbkdf2(plain, salt)
        return hmac.compare_digest(dk, test)
    except Exception:
        return False

def get_user(db, username: str) -> Optional[dict]:
    row = db.fetch_one(
        "SELECT id, username, full_name, password_hash, role FROM users WHERE username = ?",
        (username,)
    )
    if row:
        return {"id": row[0], "username": row[1], "full_name": row[2], "password_hash": row[3], "role": row[4]}
    return None

def ensure_user(db, username: str, full_name: str, role: str = 'student') -> dict:
    u = get_user(db, username)
    if u:
        return u
    db.execute(
        "INSERT INTO users(username, full_name, password_hash, role) VALUES (?,?,NULL,?)",
        (username, full_name, role)
    )
    return get_user(db, username)
