# make_mcqs_200.py
import csv, json, random
from pathlib import Path

ROOT = Path(__file__).parent
out = ROOT / "data" / "questions.csv"

# Base curated MCQs (all valid; add more here if you like)
BASE = [
    ("Which HTTP method is idempotent?", ["GET","POST","PATCH","CONNECT"], "GET", "Web", "easy"),
    ("Which creates a Flask app?", ["app = Flask(__name__)","Flask.run()","start_flask()","Flask()"], "app = Flask(__name__)", "Flask", "easy"),
    ("Which SQL join returns rows from both tables?", ["INNER JOIN","LEFT JOIN","RIGHT JOIN","FULL OUTER JOIN"], "FULL OUTER JOIN", "SQL", "medium"),
    ("Correct Python function definition?", ["function add(x,y):","def add(x,y):","func add(x,y):","def add x,y:"], "def add(x,y):", "Python", "easy"),
    ("Which status code means Not Found?", ["200","301","404","500"], "404", "Web", "easy"),
    ("Flask development server is suitable for…", ["Production","Unit tests/dev","High load","Kubernetes"], "Unit tests/dev", "Flask", "easy"),
    ("Which SQL keyword filters rows?", ["ORDER BY","GROUP BY","WHERE","LIMIT"], "WHERE", "SQL", "easy"),
    ("Python list is…", ["Immutable","Mutable","Compiled","Pointer"], "Mutable", "Python", "easy"),
    ("Which HTML tag is used for forms?", ["<div>","<form>","<table>","<input>"], "<form>", "HTML", "easy"),
    ("SQL to count rows?", ["COUNT(*)","SUM(id)","SIZE(*)","COUNT_ROWS()"], "COUNT(*)", "SQL", "easy"),
    ("Flask template engine is…", ["Jinja2","EJS","Pug","Mustache"], "Jinja2", "Flask", "easy"),
    ("Prevent SQL injection by…", ["String concat","Parameterized queries","Disable DB","Print queries"], "Parameterized queries", "SQL", "medium"),
    ("Add an element to a list?", ["list.add(x)","list.push(x)","list.append(x)","list.put(x)"], "list.append(x)", "Python", "easy"),
    ("Open a file for reading?", ["open('f','x')","open('f','w')","open('f','r')","open('f','rw')"], "open('f','r')", "Python", "easy"),
    ("CSS for responsive layout?", ["Grid/Flexbox","Tables","<center>","Marquee"], "Grid/Flexbox", "CSS", "medium"),
    ("Which HTTP status means success?", ["200","301","403","500"], "200", "Web", "easy"),
    ("Which SQL clause groups rows?", ["WHERE","GROUP BY","ORDER BY","HAVING"], "GROUP BY", "SQL", "medium"),
    ("Which keyword defines a function in Python?", ["func","function","def","lambda"], "def", "Python", "easy"),
    ("Which HTML tag defines a hyperlink?", ["<a>","<link>","<href>","<nav>"], "<a>", "HTML", "easy"),
    ("Which HTTP method is used to create a resource?", ["GET","POST","DELETE","HEAD"], "POST", "Web", "easy"),
]

# Expand to 200 by parameterized variations
topics = ["Python","SQL","HTML","CSS","Flask","Web","Git","Linux"]
difficulties = ["easy","medium","hard"]

pool = []
pool.extend(BASE)

# Generate simple, unambiguous MCQs programmatically
for n in range(1, 300):
    # Python: output of len
    s = "a"* (n%5 + 1)
    q = f"In Python, what is len('{s}')?"
    correct = str(len(s))
    wrongs = {str(len(s)+1), str(len(s)-1 if len(s)>0 else 0), str(len(s)+2)}
    opts = [correct] + list(wrongs)
    random.shuffle(opts)
    pool.append((q, opts, correct, "Python", random.choice(difficulties)))

    # SQL: aggregate
    q2 = "Which SQL function returns the number of rows?"
    opts2 = ["COUNT(*)","SUM(id)","AVG(id)","SIZE(*)"]
    pool.append((q2, opts2, "COUNT(*)", "SQL", random.choice(difficulties)))

    # Web: method safe/read-only
    q3 = "Which HTTP method is safe and read-only?"
    opts3 = ["GET","POST","PUT","DELETE"]
    pool.append((q3, opts3, "GET", "Web", random.choice(difficulties)))

    if len(pool) >= 220:  # stop when enough
        break

# Deduplicate by (prompt, answer)
seen = set()
final = []
for item in pool:
    key = (item[0], item[2])
    if key not in seen:
        final.append(item)
        seen.add(key)

# Truncate to 200
final = final[:200]

with out.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["qtype","prompt","options_json","answer","topic","difficulty","language_id","tests_json"])
    for prompt, options, answer, topic, diff in final:
        w.writerow(["mcq", prompt, json.dumps(options, ensure_ascii=False), answer, topic, diff, "", ""])

print(f"Wrote {len(final)} MCQs to {out}")
