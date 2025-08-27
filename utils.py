# utils.py
import json
def to_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)
def from_json(s: str):
    return json.loads(s) if s else None
