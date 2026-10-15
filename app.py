
from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import time
from datetime import datetime
from urllib.parse import urlparse
import requests

app = Flask(__name__)
DATABASE = "deploywatch.db"


def init_db():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                status TEXT NOT NULL,
                http_code INTEGER,
                response_time REAL,
                checked_at TEXT NOT NULL
            )
        """)


def check_application(url):
    # Only allow HTTP or HTTPS URLs.
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return "DOWN", None, 0.0

    start = time.perf_counter()

    try:
        response = requests.get(url, timeout=5)
        elapsed = round((time.perf_counter() - start) * 1000, 2)

        status = "UP" if response.ok else "DOWN"
        return status, response.status_code, elapsed

    except requests.RequestException:
        elapsed = round((time.perf_counter() - start) * 1000, 2)
        return "DOWN", None, elapsed


def save_check(url, status, http_code, response_time):
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            INSERT INTO checks
                (url, status, http_code, response_time, checked_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            url, status, http_code, response_time,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))


@app.route("/")
def dashboard():
    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory = sqlite3.Row
        history = conn.execute(
            "SELECT * FROM checks ORDER BY id DESC LIMIT 50"
        ).fetchall()

    return render_template("index.html", history=history)


@app.route("/check", methods=["POST"])
def run_check():
    url = request.form.get("url", "").strip()

    status, http_code, response_time = check_application(url)
    save_check(url, status, http_code, response_time)

    return redirect(url_for("dashboard"))


@app.route("/health")
def health():
    return {"status": "UP", "application": "DeployWatch"}, 200


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
