from __future__ import annotations

import sqlite3
import json
import os
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "crm.sqlite3"
ENV_PATH = BASE_DIR / ".env"

STATUSES = ["New Lead", "Contacted", "Meeting Scheduled", "Proposal Sent", "Negotiation", "Closed"]
OWNERS = ["Priya Sharma", "Arjun Mehta", "Neha Iyer", "Rohan Verma"]

SEED_LEADS = [
    {
        "name": "GLA University",
        "location": "Mathura, Uttar Pradesh",
        "contact": "Dr. Kavita Singh",
        "email": "kavita.singh@gla.ac.in / +91 98765 21010",
        "type": "Private University",
        "strength": 6400,
        "interest": "AI/ML Industry Initiative",
        "source": "Past Partnership",
        "status": "Negotiation",
        "owner": "Priya Sharma",
        "last_touch": "2026-06-21",
    },
    {
        "name": "Ramaiah Institute of Technology",
        "location": "Bengaluru, Karnataka",
        "contact": "Prof. Nikhil Rao",
        "email": "nikhil.rao@msrit.edu / +91 98450 11442",
        "type": "Engineering College",
        "strength": 5200,
        "interest": "Cloud & DevOps Workshop",
        "source": "Education Expo",
        "status": "Meeting Scheduled",
        "owner": "Neha Iyer",
        "last_touch": "2026-06-24",
    },
    {
        "name": "Patna Women's College",
        "location": "Patna, Bihar",
        "contact": "Ms. Ananya Sinha",
        "email": "ananya.sinha@pwcpatna.edu.in / +91 91223 77190",
        "type": "Autonomous Institute",
        "strength": 3100,
        "interest": "Placement Readiness Program",
        "source": "LinkedIn Outreach",
        "status": "Contacted",
        "owner": "Arjun Mehta",
        "last_touch": "2026-06-19",
    },
    {
        "name": "Government Engineering College Ajmer",
        "location": "Ajmer, Rajasthan",
        "contact": "Dr. Mahesh Jain",
        "email": "trainingcell@gecajmer.ac.in / +91 94140 88021",
        "type": "Government College",
        "strength": 2300,
        "interest": "Cybersecurity Training",
        "source": "Referral",
        "status": "New Lead",
        "owner": "Rohan Verma",
        "last_touch": "2026-06-25",
    },
]

app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")


def load_env_file() -> None:
    if not ENV_PATH.exists():
        return
    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()
AI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def ai_available() -> bool:
    return OpenAI is not None and bool(os.getenv("OPENAI_API_KEY"))


def fallback_intelligence(lead: dict | sqlite3.Row) -> dict:
    score = score_lead(lead)
    return {
        "score": score,
        "priority": priority_label(score),
        "nextBestAction": next_best_action(lead),
        "outreachMessage": generate_message(lead),
        "followUpSuggestion": (
            f"Contact {lead['contact']} within 24 hours and offer two meeting slots with a sample training calendar."
        ),
        "aiSource": "rules",
    }


def generate_ai_intelligence(lead: dict | sqlite3.Row) -> dict:
    fallback = fallback_intelligence(lead)
    if not ai_available():
        return fallback

    client = OpenAI()
    prompt = {
        "institution": lead["name"],
        "location": lead["location"],
        "contact_person": lead["contact"],
        "email_phone": lead["email"],
        "institution_type": lead["type"],
        "student_strength": lead["strength"],
        "program_interest": lead["interest"],
        "lead_source": lead["source"],
        "lead_status": lead["status"],
        "sales_owner": lead["owner"],
    }
    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            temperature=0.4,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI sales analyst for a B2B academia training company. "
                        "Return only valid JSON with keys: score, priority, nextBestAction, "
                        "outreachMessage, followUpSuggestion. Score must be an integer 0-100. "
                        "Priority must be High, Medium, or Low. Make the outreach message concise, "
                        "specific to the institution, and professional."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Analyze this institution lead for technical training partnership sales:\n"
                        f"{json.dumps(prompt, ensure_ascii=True)}"
                    ),
                },
            ],
        )
        content = response.choices[0].message.content or "{}"
        result = json.loads(content)
        score = int(result.get("score", fallback["score"]))
        score = max(0, min(score, 100))
        priority = result.get("priority") if result.get("priority") in ["High", "Medium", "Low"] else priority_label(score)
        return {
            "score": score,
            "priority": priority,
            "nextBestAction": str(result.get("nextBestAction") or fallback["nextBestAction"]),
            "outreachMessage": str(result.get("outreachMessage") or fallback["outreachMessage"]),
            "followUpSuggestion": str(result.get("followUpSuggestion") or fallback["followUpSuggestion"]),
            "aiSource": f"openai:{AI_MODEL}",
        }
    except Exception as exc:
        fallback["aiSource"] = f"rules-fallback:{exc.__class__.__name__}"
        return fallback


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT NOT NULL,
                contact TEXT NOT NULL,
                email TEXT NOT NULL,
                type TEXT NOT NULL,
                strength INTEGER NOT NULL,
                interest TEXT NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                owner TEXT NOT NULL,
                last_touch TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                lead_id INTEGER,
                lead_name TEXT NOT NULL,
                owner TEXT NOT NULL,
                due TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            )
            """
        )
        lead_count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        if lead_count == 0:
            conn.executemany(
                """
                INSERT INTO leads
                (name, location, contact, email, type, strength, interest, source, status, owner, last_touch)
                VALUES
                (:name, :location, :contact, :email, :type, :strength, :interest, :source, :status, :owner, :last_touch)
                """,
                SEED_LEADS,
            )
            seed_tasks(conn)


def seed_tasks(conn: sqlite3.Connection) -> None:
    leads = conn.execute("SELECT * FROM leads ORDER BY id LIMIT 3").fetchall()
    for index, lead in enumerate(leads):
        create_task(conn, next_best_action(lead), lead, "Today" if index == 0 else f"In {index + 1} days")


def row_to_lead(row: sqlite3.Row) -> dict:
    lead = dict(row)
    lead["lastTouch"] = lead.pop("last_touch")
    lead.update(generate_ai_intelligence(lead))
    return lead


def row_to_task(row: sqlite3.Row) -> dict:
    task = dict(row)
    task["lead"] = task.pop("lead_name")
    task["createdAt"] = task.pop("created_at")
    task.pop("lead_id", None)
    return task


def score_lead(lead: dict | sqlite3.Row) -> int:
    score = 35
    strength = int(lead["strength"])
    if strength >= 5000:
        score += 25
    elif strength >= 3000:
        score += 15
    if lead["source"] == "Past Partnership":
        score += 20
    if lead["interest"] in ["AI/ML Industry Initiative", "Cloud & DevOps Workshop"]:
        score += 10
    if lead["status"] in ["Meeting Scheduled", "Proposal Sent", "Negotiation"]:
        score += 10
    return min(score, 100)


def priority_label(score: int) -> str:
    if score >= 80:
        return "High"
    if score >= 60:
        return "Medium"
    return "Low"


def next_best_action(lead: dict | sqlite3.Row) -> str:
    return {
        "New Lead": "Assign owner and send first outreach today",
        "Contacted": "Schedule discovery meeting with training cell",
        "Meeting Scheduled": "Prepare agenda and program fit notes",
        "Proposal Sent": "Follow up on budget, dates, and approvals",
        "Negotiation": "Share final commercial terms and close plan",
        "Closed": "Kick off delivery onboarding",
    }[lead["status"]]


def generate_message(lead: dict | sqlite3.Row) -> str:
    score = score_lead(lead)
    strength = f"{int(lead['strength']):,}"
    return (
        f"Hello {lead['contact']},\n\n"
        f"We noticed {lead['name']} has a strong fit for our {lead['interest'].lower()} initiative, "
        f"especially with {strength} students and your institution profile in {lead['location']}.\n\n"
        "Based on similar academia partnerships, we can help run a practical, industry-led program covering "
        "curriculum alignment, hands-on workshops, mentor sessions, and placement-focused outcomes.\n\n"
        "Would you be open to a 30-minute discussion this week to map student readiness goals and a possible rollout plan?\n\n"
        f"AI priority: {priority_label(score)} ({score}/100)\n"
        f"Suggested next step: {next_best_action(lead)}"
    )


def create_task(conn: sqlite3.Connection, title: str, lead: dict | sqlite3.Row, due: str) -> None:
    conn.execute(
        """
        INSERT INTO tasks (title, lead_id, lead_name, owner, due, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (title, lead["id"], lead["name"], lead["owner"], due, date.today().isoformat()),
    )


def validate_lead(payload: dict, partial: bool = False) -> tuple[dict, str | None]:
    fields = ["name", "location", "contact", "email", "type", "strength", "interest", "source", "status"]
    data = {}
    for field in fields:
        if field not in payload:
            if not partial:
                return {}, f"Missing required field: {field}"
            continue
        data[field] = payload[field]
    if "strength" in data:
        try:
            data["strength"] = int(data["strength"])
        except (TypeError, ValueError):
            return {}, "Student strength must be a number"
    if "status" in data and data["status"] not in STATUSES:
        return {}, "Invalid lead status"
    return data, None


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/api/leads")
def list_leads():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
    return jsonify([row_to_lead(row) for row in rows])


@app.post("/api/leads")
def create_lead():
    payload, error = validate_lead(request.get_json(silent=True) or {})
    if error:
        return jsonify({"error": error}), 400
    with get_db() as conn:
        owner = OWNERS[conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0] % len(OWNERS)]
        cursor = conn.execute(
            """
            INSERT INTO leads
            (name, location, contact, email, type, strength, interest, source, status, owner, last_touch)
            VALUES
            (:name, :location, :contact, :email, :type, :strength, :interest, :source, :status, :owner, :last_touch)
            """,
            {**payload, "owner": owner, "last_touch": date.today().isoformat()},
        )
        lead = conn.execute("SELECT * FROM leads WHERE id = ?", (cursor.lastrowid,)).fetchone()
        create_task(conn, "Send AI-personalized first outreach", lead, "Today")
    return jsonify(row_to_lead(lead)), 201


@app.patch("/api/leads/<int:lead_id>")
def update_lead(lead_id: int):
    payload, error = validate_lead(request.get_json(silent=True) or {}, partial=True)
    if error:
        return jsonify({"error": error}), 400
    if not payload:
        return jsonify({"error": "No fields supplied"}), 400
    assignments = ", ".join(f"{field} = ?" for field in payload)
    values = list(payload.values()) + [date.today().isoformat(), lead_id]
    with get_db() as conn:
        current = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if current is None:
            return jsonify({"error": "Lead not found"}), 404
        conn.execute(f"UPDATE leads SET {assignments}, last_touch = ? WHERE id = ?", values)
        lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        create_task(conn, next_best_action(lead), lead, "Today")
    return jsonify(row_to_lead(lead))


@app.post("/api/leads/<int:lead_id>/advance")
def advance_lead(lead_id: int):
    with get_db() as conn:
        lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if lead is None:
            return jsonify({"error": "Lead not found"}), 404
        status_index = STATUSES.index(lead["status"])
        next_status = STATUSES[min(status_index + 1, len(STATUSES) - 1)]
        conn.execute("UPDATE leads SET status = ?, last_touch = ? WHERE id = ?", (next_status, date.today().isoformat(), lead_id))
        lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        create_task(conn, next_best_action(lead), lead, "Today")
    return jsonify(row_to_lead(lead))


@app.get("/api/tasks")
def list_tasks():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tasks ORDER BY id DESC LIMIT 12").fetchall()
    return jsonify([row_to_task(row) for row in rows])


@app.post("/api/tasks")
def add_task():
    payload = request.get_json(silent=True) or {}
    lead_id = payload.get("leadId")
    with get_db() as conn:
        lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if lead is None:
            return jsonify({"error": "Lead not found"}), 404
        create_task(conn, payload.get("title") or f"Follow up with {lead['contact']}", lead, payload.get("due") or "Tomorrow")
        task = conn.execute("SELECT * FROM tasks ORDER BY id DESC LIMIT 1").fetchone()
    return jsonify(row_to_task(task)), 201


@app.post("/api/ai-review")
def ai_review():
    with get_db() as conn:
        leads = conn.execute("SELECT * FROM leads").fetchall()
        ranked = sorted(leads, key=score_lead, reverse=True)
        conn.execute("DELETE FROM tasks")
        for index, lead in enumerate(ranked):
            title = "Priority review: close next step" if index == 0 else next_best_action(lead)
            due = "Today" if index < 2 else "This week"
            create_task(conn, title, lead, due)
        tasks = conn.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
    return jsonify({"leads": [row_to_lead(lead) for lead in ranked], "tasks": [row_to_task(task) for task in tasks]})


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="127.0.0.1", port=5000, use_reloader=False)
