# app.py
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import time, json
from pathlib import Path

from db import DB
from auth import get_user, check_password, hash_password
from utils import to_json
from reports import make_pdf

st.set_page_config(page_title="Mock Test App", page_icon="✅", layout="wide")
DBI = DB()

# ------------------ AUTO INIT (for Render free tier) ------------------
def _db_is_empty():
    try:
        row = DBI.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='questions'"
        )
        if not row:
            return True
        cnt = DBI.fetch_one("SELECT COUNT(*) FROM questions")[0]
        return (cnt or 0) == 0
    except Exception:
        return True

if _db_is_empty():
    # Create schema
    DBI.run_script(Path(__file__).parent / "schema.sql")

    # Seed users
    import csv
    users_csv = Path(__file__).parent / "data" / "users.csv"
    if users_csv.exists():
        with users_csv.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pwd = row.get("password") or ""
                DBI.execute(
                    "INSERT OR IGNORE INTO users(username, full_name, password_hash, role) VALUES (?,?,?,?)",
                    (
                        row["username"],
                        row["full_name"],
                        hash_password(pwd) if pwd else None,
                        "student",
                    ),
                )
    if not DBI.fetch_one("SELECT 1 FROM users WHERE username='admin'"):
        DBI.execute(
            "INSERT INTO users(username, full_name, password_hash, role) VALUES (?,?,?,?)",
            ("admin", "Administrator", hash_password("admin123"), "admin"),
        )

    # Seed questions
    q_csv = Path(__file__).parent / "data" / "questions.csv"
    if q_csv.exists():
        with q_csv.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                DBI.execute(
                    "INSERT INTO questions(qtype,prompt,options_json,answer,topic,difficulty,marks,language_id,tests_json) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        (row.get("qtype") or "mcq").lower(),
                        row.get("prompt"),
                        row.get("options_json"),
                        row.get("answer"),
                        row.get("topic"),
                        (row.get("difficulty") or "medium").lower(),
                        int(row.get("marks") or 1),
                        row.get("language_id"),
                        row.get("tests_json"),
                    ),
                )
# ----------------------------------------------------------------------

# ---- Session ----
ss = st.session_state
ss.setdefault("user", None)
ss.setdefault("attempt_id", None)
ss.setdefault("selected", {})
ss.setdefault("deadline", None)
ss.setdefault("current_qs", [])

# ---- Helpers ----
def safe_json_list(s):
    try:
        if not s:
            return None
        v = json.loads(s)
        return v if isinstance(v, list) else None
    except Exception:
        return None

def mcq_radio(options, key):
    """Radio with a hidden label (no warnings)."""
    return st.radio(
        "Select one option", options, index=None, key=key, label_visibility="collapsed"
    )

def load_mcqs_df():
    rows = DBI.fetch_all(
        "SELECT id,qtype,prompt,options_json,answer,topic,difficulty,marks FROM questions"
    )
    df = pd.DataFrame(
        rows,
        columns=[
            "id",
            "qtype",
            "prompt",
            "options_json",
            "answer",
            "topic",
            "difficulty",
            "marks",
        ],
    )
    if df.empty:
        return df
    df["qtype"] = df["qtype"].astype(str).str.lower()
    df["difficulty"] = df["difficulty"].astype(str).str.lower()
    df = df[df.qtype == "mcq"].copy()
    valid_rows = []
    for _, r in df.iterrows():
        opts = safe_json_list(r["options_json"])
        if isinstance(opts, list) and len(opts) == 4 and r["answer"] in opts:
            valid_rows.append(
                {
                    "id": r["id"],
                    "prompt": r["prompt"],
                    "options": opts,
                    "answer": r["answer"],
                    "topic": r["topic"],
                    "difficulty": (r["difficulty"] or "medium"),
                    "marks": int(r["marks"]) if pd.notna(r["marks"]) else 1,
                }
            )
    return pd.DataFrame(valid_rows)

def prior_accuracy(user_id: int) -> float:
    row = DBI.fetch_one(
        "SELECT AVG(r.is_correct) FROM responses r JOIN attempts a ON a.id=r.attempt_id WHERE a.user_id=?",
        (user_id,),
    )
    return float(row[0]) if row and row[0] is not None else 0.5

def difficulty_weights(acc: float):
    if acc < 0.5:
        return {"easy": 0.6, "medium": 0.3, "hard": 0.1}
    if acc < 0.8:
        return {"easy": 0.3, "medium": 0.5, "hard": 0.2}
    return {"easy": 0.2, "medium": 0.4, "hard": 0.4}

def weighted_take(df, n, weights):
    if df.empty or n <= 0:
        return df.head(0)
    pools = {
        d: df[df.difficulty == d].sample(frac=1, random_state=None)
        for d in ["easy", "medium", "hard"]
    }
    counts = {d: max(0, int(n * weights.get(d, 0))) for d in pools}
    while sum(counts.values()) < n:
        d = max(weights, key=weights.get)
        counts[d] += 1
    out = []
    for d, cnt in counts.items():
        if cnt > 0 and not pools[d].empty:
            out.append(pools[d].head(cnt))
    res = pd.concat(out) if out else df.head(0)
    if len(res) < n:
        rest = df.drop(res.index, errors="ignore").sample(frac=1, random_state=None)
        res = pd.concat([res, rest.head(n - len(res))])
    return res.head(n)

def pick_questions(user_id: int, n: int):
    df = load_mcqs_df()
    if df.empty:
        return []
    acc = prior_accuracy(user_id)
    weights = difficulty_weights(acc)
    chosen = weighted_take(df, n, weights)
    chosen = chosen.drop_duplicates(subset=["id"])
    if len(chosen) < n:
        leftovers = df[~df.id.isin(set(chosen.id))].sample(frac=1, random_state=None)
        chosen = pd.concat([chosen, leftovers.head(n - len(chosen))])
    return chosen.head(n).to_dict("records")

def start_attempt(user, n_questions: int, time_limit_min: int):
    qs = pick_questions(user["id"], n_questions)
    DBI.execute(
        "INSERT INTO attempts(user_id, time_limit_minutes, questions_json) VALUES (?,?,?)",
        (user["id"], time_limit_min, to_json([q["id"] for q in qs])),
    )
    attempt_id = DBI.fetch_one("SELECT last_insert_rowid()", ())[0]
    ss.attempt_id = attempt_id
    ss.current_qs = qs
    ss.selected = {}
    ss.deadline = (datetime.now() + timedelta(minutes=time_limit_min)).isoformat()

def finalize_attempt():
    if not ss.attempt_id:
        return
    for idx, q in enumerate(ss.current_qs):
        key = f"q_{idx}_{q['id']}"
        resp = st.session_state.selected.get(key)
        is_correct = 1 if (resp is not None and str(resp) == str(q["answer"])) else 0
        DBI.execute(
            "INSERT INTO responses(attempt_id, question_id, response, is_correct) VALUES (?,?,?,?)",
            (ss.attempt_id, q["id"], str(resp) if resp is not None else None, is_correct),
        )
    DBI.execute(
        "UPDATE attempts SET completed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (ss.attempt_id,),
    )
    ss.attempt_id = None
    ss.selected = {}
    ss.current_qs = []
    ss.deadline = None

def render_timer_and_get_tick():
    if not ss.deadline:
        return False
    remaining = datetime.fromisoformat(ss.deadline) - datetime.now()
    secs = max(0, int(remaining.total_seconds()))
    mm, ss_rem = divmod(secs, 60)
    st.sidebar.metric("Time Left", f"{mm:02d}:{ss_rem:02d}")
    if secs <= 0 and st.session_state.get("attempt_id"):
        st.warning("Time is up! Auto-submitting…")
        finalize_attempt()
        return False
    return True

# ---- Auth ----
st.sidebar.title("Mock Test")
if not ss.user:
    st.header("Login")
    username = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    if st.button("Sign In", type="primary"):
        u = get_user(DBI, username)
        if not u:
            st.error("User not found")
        elif not u.get("password_hash"):
            st.error("This account has no password set.")
        elif check_password(pwd, u["password_hash"]):
            ss.user = u
            st.success(f"Welcome, {u['full_name']}")
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.info("Admin: admin/admin123")
    st.stop()

user = ss.user

# ---- Sidebar: logged-in info + Logout ----
st.sidebar.success(f"Logged in as {user['full_name']} ({user['role']})")
if st.sidebar.button("🚪 Logout", use_container_width=True):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.user = None
    st.rerun()

# ---- Role-based navigation ----
nav_pages = ["Take Test", "My Analysis"]
if user["role"] == "admin":
    nav_pages.append("Admin")
page = st.sidebar.radio("Go to", nav_pages)

# ---- Take Test ----
if page == "Take Test":
    st.header("Take Test")
    with st.form("config_form"):
        num_q = st.number_input("Number of questions", 3, 50, 10, 1)
        time_limit = st.number_input("Time limit (minutes)", 5, 120, 15, 5)
        if st.form_submit_button("Start New Attempt", type="primary"):
            start_attempt(user, int(num_q), int(time_limit))
            st.success("Attempt started. Scroll to answer.")

    if ss.attempt_id:
        render_timer_and_get_tick()
        st.subheader("Questions")

        if not ss.current_qs:
            st.error("No valid MCQs available. Re-seed questions.csv.")
        else:
            for i, q in enumerate(ss.current_qs, start=1):
                st.markdown(
                    f"**Q{i}. [{q.get('topic','')}]** {q['prompt']} "
                    f"&nbsp;<span style='color:#64748b'>(Marks: {q['marks']})</span>",
                    unsafe_allow_html=True,
                )
                key = f"q_{i-1}_{q['id']}"
                ss.selected[key] = mcq_radio(q["options"], key)
                st.divider()

            if st.button("Submit Attempt", type="primary"):
                finalize_attempt()
                st.success("Submitted! Go to **My Analysis** for results.")

# ---- My Analysis ----
if page == "My Analysis":
    st.header("My Analysis")
    last = DBI.fetch_one(
        "SELECT id FROM attempts WHERE user_id=? AND completed_at IS NOT NULL ORDER BY completed_at DESC LIMIT 1",
        (user["id"],),
    )
    if last:
        rows = DBI.fetch_all(
            "SELECT r.is_correct,q.marks,q.topic FROM responses r JOIN questions q ON q.id=r.question_id WHERE r.attempt_id=?",
            (last[0],),
        )
        df_last = pd.DataFrame(rows, columns=["is_correct", "marks", "topic"])
        obtained = int((df_last["is_correct"] * df_last["marks"]).sum())
        total = int(df_last["marks"].sum())
        st.subheader(f"Score (last attempt): **{obtained} / {total}**")

    df_resp = pd.DataFrame(
        DBI.fetch_all(
            "SELECT a.user_id,r.question_id,r.is_correct FROM responses r JOIN attempts a ON a.id=r.attempt_id WHERE a.user_id=?",
            (user["id"],),
        ),
        columns=["user_id", "question_id", "is_correct"],
    )
    if not df_resp.empty:
        df_q = pd.DataFrame(DBI.fetch_all("SELECT id,topic FROM questions"), columns=["id", "topic"])
        df = df_resp.merge(df_q, left_on="question_id", right_on="id", how="left")
        topic_acc = (
            df.groupby("topic")["is_correct"]
            .mean()
            .fillna(0)
            .reset_index()
            .rename(columns={"is_correct": "accuracy"})
        )
        st.metric("Overall Accuracy", f"{(df['is_correct'].mean()*100):.1f}%")
        st.bar_chart(topic_acc.set_index("topic"))

# ---- Admin ----
if page == "Admin" and user["role"] == "admin":
    st.header("Admin Panel")

    urows = DBI.fetch_all("SELECT id,username,full_name FROM users ORDER BY username")
    df_users = pd.DataFrame(urows, columns=["user_id", "username", "full_name"])
    rrows = DBI.fetch_all(
        "SELECT a.user_id,r.question_id,r.is_correct,a.id as attempt_id,a.completed_at FROM responses r JOIN attempts a ON a.id=r.attempt_id"
    )
    df_resp = pd.DataFrame(
        rrows, columns=["user_id", "question_id", "is_correct", "attempt_id", "completed_at"]
    )
    qrows = DBI.fetch_all("SELECT id,topic,marks FROM questions")
    df_q = pd.DataFrame(qrows, columns=["question_id", "topic", "marks"])

    if not df_resp.empty:
        df = df_resp.merge(df_q, on="question_id", how="left")
        attempts_scores = df.groupby(["user_id", "attempt_id"], as_index=False).agg(
            obtained=("is_correct", "sum"),
            max_marks=("marks", "sum"),
            completed_at=("completed_at", "max"),
        )
        per_user = (
            attempts_scores.sort_values("completed_at")
            .groupby("user_id")
            .agg(
                attempts=("attempt_id", "nunique"),
                last_obtained=("obtained", "last"),
                last_max=("max_marks", "last"),
                last_completed=("completed_at", "last"),
            )
            .reset_index()
        )
        acc_overall = (
            df.groupby("user_id")["is_correct"].mean().reset_index().rename(columns={"is_correct": "accuracy"})
        )
        table = df_users.merge(per_user, on="user_id", how="left").merge(
            acc_overall, on="user_id", how="left"
        )
        table["accuracy"] = (table["accuracy"] * 100).round(1)
        table.fillna({"attempts": 0, "last_obtained": 0, "last_max": 0, "accuracy": 0}, inplace=True)

        st.dataframe(
            table.rename(
                columns={
                    "username": "Username",
                    "full_name": "Name",
                    "attempts": "Attempts",
                    "last_obtained": "Last Score",
                    "last_max": "Last Max",
                    "accuracy": "Accuracy %",
                    "last_completed": "Last Completed",
                }
            ),
            use_container_width=True,
        )

        sel_user = st.selectbox("Choose a student for PDF", table["Username"].tolist())
        if sel_user:
            urec = df_users[df_users.username == sel_user].iloc[0]
            df_student = df[df.user_id == urec.user_id]
            topic_user = df_student.groupby("topic")["is_correct"].mean()
            topic_class = df.groupby("topic")["is_correct"].mean()
            comp = pd.concat([topic_user.rename("user"), topic_class.rename("class")], axis=1).fillna(0).reset_index()
            topic_rows = list(topic_user.reset_index().itertuples(index=False, name=None))
            comp_rows = [(r[0], r[1], r[2]) for r in comp.itertuples(index=False, name=None)]
            overall_user = float(df_student["is_correct"].mean() or 0) * 100
            pdf_bytes = make_pdf(
                {"username": urec.username, "full_name": urec.full_name},
                overall_user,
                topic_rows,
                comp_rows,
            )
            st.download_button(
                "Download PDF Report",
                data=pdf_bytes,
                file_name=f"report_{urec.username}.pdf",
                mime="application/pdf",
            )

        export_df = df.merge(df_users, on="user_id", how="left").merge(df_q, on="question_id", how="left")
        st.download_button(
            "Download Class Results (CSV)",
            export_df.to_csv(index=False),
            file_name="results.csv",
            mime="text/csv",
        )

# ---- Timer rerun ----
if ss.get("attempt_id") and ss.get("deadline"):
    remaining = datetime.fromisoformat(ss.deadline) - datetime.now()
    if remaining.total_seconds() > 0:
        time.sleep(1)
        st.rerun()
