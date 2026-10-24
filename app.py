
from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import time
import threading
from datetime import datetime
from urllib.parse import urlparse
from contextlib import closing

import requests

app = Flask(__name__)

DATABASE = "deploywatch.db"
CHECK_INTERVAL = 30
monitor_started = False
monitor_lock = threading.Lock()


def get_connection():
    return sqlite3.connect(DATABASE, timeout=10)


def init_db():
    with closing(get_connection()) as conn:
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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS monitored_urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def check_application(url):
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return "DOWN", None, 0.0

    start = time.perf_counter()

    try:
        response = requests.get(
            url,
            timeout=5,
            allow_redirects=True
        )
        elapsed = round(
            (time.perf_counter() - start) * 1000, 2
        )
        status = "UP" if response.ok else "DOWN"

        return status, response.status_code, elapsed

    except requests.RequestException:
        elapsed = round(
            (time.perf_counter() - start) * 1000, 2
        )
        return "DOWN", None, elapsed


def save_check(url, status, http_code, response_time):
    with closing(get_connection()) as conn:
        conn.execute("""
            INSERT INTO checks
                (url, status, http_code, response_time, checked_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            url,
            status,
            http_code,
            response_time,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()


def get_monitored_urls():
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("""
            SELECT m.id, m.url, m.enabled, m.created_at,
                   c.status, c.http_code, c.response_time,
                   c.checked_at
            FROM monitored_urls AS m
            LEFT JOIN checks AS c
              ON c.id = (
                  SELECT MAX(c2.id)
                  FROM checks AS c2
                  WHERE c2.url = m.url
              )
            ORDER BY m.id DESC
        """).fetchall()


def monitor_loop():
    while True:
        try:
            with closing(get_connection()) as conn:
                urls = conn.execute("""
                    SELECT url FROM monitored_urls
                    WHERE enabled = 1
                """).fetchall()

            for (url,) in urls:
                status, code, response_time = check_application(url)
                save_check(url, status, code, response_time)

        except Exception as exc:
            app.logger.exception(
                "Automatic monitoring encountered an error: %s", exc
            )

        time.sleep(CHECK_INTERVAL)


def start_monitor():
    global monitor_started

    with monitor_lock:
        if monitor_started:
            return

        thread = threading.Thread(
            target=monitor_loop,
            name="deploywatch-monitor",
            daemon=True
        )
        thread.start()
        monitor_started = True


@app.route("/")
def dashboard():
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        history = conn.execute("""
            SELECT * FROM checks
            ORDER BY id DESC LIMIT 50
        """).fetchall()

    monitored_urls = get_monitored_urls()

    return render_template(
        "index.html",
        history=history,
        monitored_urls=monitored_urls,
        check_interval=CHECK_INTERVAL
    )


@app.route("/add", methods=["POST"])
def add_url():
    url = request.form.get("url", "").strip()
    parsed = urlparse(url)

    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        return "Enter a valid HTTP or HTTPS URL.", 400

    try:
        with closing(get_connection()) as conn:
            conn.execute("""
                INSERT OR IGNORE INTO monitored_urls
                    (url, enabled, created_at)
                VALUES (?, 1, ?)
            """, (
                url,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            conn.commit()

        # Run the first check immediately.
        status, code, response_time = check_application(url)
        save_check(url, status, code, response_time)

    except sqlite3.Error:
        app.logger.exception("Could not save monitored URL")
        return "Could not save this URL. Check the application logs.", 500

    return redirect(url_for("dashboard"))


@app.route("/check", methods=["POST"])
def run_check():
    url = request.form.get("url", "").strip()
    status, http_code, response_time = check_application(url)
    save_check(url, status, http_code, response_time)
    return redirect(url_for("dashboard"))


@app.route("/monitor/<int:url_id>/toggle", methods=["POST"])
def toggle_monitor(url_id):
    with closing(get_connection()) as conn:
        conn.execute("""
            UPDATE monitored_urls
            SET enabled = CASE enabled WHEN 1 THEN 0 ELSE 1 END
            WHERE id = ?
        """, (url_id,))
        conn.commit()

    return redirect(url_for("dashboard"))


@app.route("/health")
def health():
    return {"status": "UP", "application": "DeployWatch"}, 200


if __name__ == "__main__":
    init_db()
    start_monitor()
    app.run(host="0.0.0.0", port=5000, debug=False)
