"""
api.py — Flask REST API for the FinFlow dashboard.

Exposes the following endpoints:

  GET  /api/rates              — current rate + 24h change for all 7 GBP pairs
  GET  /api/history/<pair>     — up to 180 days of rate history for one pair
  GET  /api/alerts             — all active alert thresholds
  POST /api/alerts             — create a new alert threshold
  DELETE /api/alerts/<id>      — remove an alert threshold by ID
  GET  /api/status             — database connection, last fetch time, alert count

Run from the repo root:
  python finflow/api.py

The server starts on localhost:5001.
Port 5001 avoids conflict with macOS AirPlay Receiver which occupies port 5000.
"""
from flask import Flask, jsonify, request, send_from_directory
import sqlite3
from datetime import datetime
from flask import Flask, jsonify, request
from config import DATABASE_FILE, PAIR_STRINGS, API_PORT
from storage import (
    init_database,
    get_all_latest_rates,
    get_rate_history,
)

# ── App setup ─────────────────────────────────────────────────────────────────

app = Flask(__name__)

# Ensure the database and its tables exist before the first request is handled
init_database()


# ── Helper ────────────────────────────────────────────────────────────────────

def error(message: str, status: int):
    """
    Return a JSON error response with a consistent shape.

    Args:
        message: Human-readable error description
        status:  HTTP status code (e.g. 400, 404, 500)
    """
    return jsonify({"error": message}), status


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/rates", methods=["GET"])
def get_rates():
    """
    Return the current rate and 24h change for all 7 tracked GBP pairs.

    Response shape:
    [
      {
        "pair":       "GBP/USD",
        "rate":       1.3165,
        "previous":   1.3120,
        "change_pct": 0.34,
        "timestamp":  "2026-06-07T19:02:27"
      },
      ...
    ]

    Pairs with no stored data are included with null values so the
    dashboard can show placeholders rather than crashing.
    """
    try:
        rates = get_all_latest_rates(db_path=DATABASE_FILE)
        return jsonify(rates), 200
    except Exception as e:
        return error(f"Failed to fetch rates: {str(e)}", 500)


@app.route("/api/history/<path:pair>", methods=["GET"])
def get_history(pair: str):
    """
    Return time-series rate data for a single currency pair.

    URL example: /api/history/GBP/USD

    Flask's <path:pair> matcher captures the slash in 'GBP/USD',
    so the URL reads naturally without encoding.

    Optional query parameter:
      days (int) — number of days of history to return (default: 180, max: 180)

    Response shape:
    [
      {"timestamp": "2026-01-01T09:00:00", "rate": 1.3100},
      {"timestamp": "2026-01-02T09:00:00", "rate": 1.3120},
      ...
    ]
    """
    # Validate the pair is one we actually track
    pair_upper = pair.upper()
    if pair_upper not in PAIR_STRINGS:
        return error(
            f"Unknown pair '{pair}'. Valid pairs: {', '.join(PAIR_STRINGS)}", 400
        )

    # Parse optional 'days' query parameter, cap at 180
    try:
        days = int(request.args.get("days", 180))
        days = min(days, 180)
    except ValueError:
        return error("'days' must be an integer", 400)

    try:
        history = get_rate_history(pair_upper, days=days, db_path=DATABASE_FILE)
        return jsonify(history), 200
    except ValueError as e:
        return error(str(e), 400)
    except Exception as e:
        return error(f"Failed to fetch history: {str(e)}", 500)


@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    """
    Return all active alert thresholds stored in the database.

    Response shape:
    [
      {
        "id":             1,
        "pair":           "GBP/USD",
        "threshold_low":  1.25,
        "threshold_high": 1.35
      },
      ...
    ]
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, from_currency, to_currency, threshold_low, threshold_high
            FROM alert_thresholds
            ORDER BY id ASC
        """)

        rows = cursor.fetchall()
        conn.close()

        alerts = [
            {
                "id":             row["id"],
                "pair":           f"{row['from_currency']}/{row['to_currency']}",
                "threshold_low":  row["threshold_low"],
                "threshold_high": row["threshold_high"],
            }
            for row in rows
        ]

        return jsonify(alerts), 200

    except Exception as e:
        return error(f"Failed to fetch alerts: {str(e)}", 500)


@app.route("/api/alerts", methods=["POST"])
def create_alert():
    """
    Create or update an alert threshold for a currency pair.

    Expected JSON body:
    {
      "pair":           "GBP/USD",     (required)
      "threshold_low":  1.25,          (optional, but at least one threshold required)
      "threshold_high": 1.35           (optional, but at least one threshold required)
    }

    Returns the created/updated alert with its database ID.
    Uses INSERT OR REPLACE so re-posting for the same pair updates it
    rather than creating a duplicate.
    """
    data = request.get_json(silent=True)

    if not data:
        return error("Request body must be JSON", 400)

    pair = data.get("pair", "").upper()
    if pair not in PAIR_STRINGS:
        return error(
            f"Unknown pair '{pair}'. Valid pairs: {', '.join(PAIR_STRINGS)}", 400
        )

    threshold_low  = data.get("threshold_low")
    threshold_high = data.get("threshold_high")

    # At least one threshold must be provided
    if threshold_low is None and threshold_high is None:
        return error("Provide at least one of 'threshold_low' or 'threshold_high'", 400)

    # Validate threshold values are positive numbers
    if threshold_low is not None:
        if not isinstance(threshold_low, (int, float)) or threshold_low <= 0:
            return error("'threshold_low' must be a positive number", 400)

    if threshold_high is not None:
        if not isinstance(threshold_high, (int, float)) or threshold_high <= 0:
            return error("'threshold_high' must be a positive number", 400)

    # If both provided, low must be less than high
    if threshold_low is not None and threshold_high is not None:
        if threshold_low >= threshold_high:
            return error("'threshold_low' must be less than 'threshold_high'", 400)

    # Split pair string back into individual currency codes for storage
    from_currency, to_currency = pair.split("/")

    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # INSERT OR REPLACE updates the row if the pair already exists
        cursor.execute("""
            INSERT OR REPLACE INTO alert_thresholds
                (from_currency, to_currency, threshold_low, threshold_high)
            VALUES (?, ?, ?, ?)
        """, (from_currency, to_currency, threshold_low, threshold_high))

        alert_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({
            "id":             alert_id,
            "pair":           pair,
            "threshold_low":  threshold_low,
            "threshold_high": threshold_high,
        }), 201

    except Exception as e:
        return error(f"Failed to create alert: {str(e)}", 500)


@app.route("/api/alerts/<int:alert_id>", methods=["DELETE"])
def delete_alert(alert_id: int):
    """
    Delete an alert threshold by its database ID.

    Returns 404 if the ID does not exist, 204 No Content on success.
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Check the alert actually exists before attempting deletion
        cursor.execute(
            "SELECT id FROM alert_thresholds WHERE id = ?", (alert_id,)
        )
        if cursor.fetchone() is None:
            conn.close()
            return error(f"Alert ID {alert_id} not found", 404)

        cursor.execute(
            "DELETE FROM alert_thresholds WHERE id = ?", (alert_id,)
        )
        conn.commit()
        conn.close()

        # 204 No Content is the conventional response for a successful DELETE
        return "", 204

    except Exception as e:
        return error(f"Failed to delete alert: {str(e)}", 500)


@app.route("/api/status", methods=["GET"])
def get_status():
    """
    Return the current operational status of the FinFlow backend.

    Response shape:
    {
      "db_connected":  true,
      "db_path":       "/path/to/finflow.db",
      "last_fetch":    "2026-06-07T19:02:27",   (or null if no data yet)
      "alert_count":   2,
      "tracked_pairs": 7
    }

    db_connected will be false if the database file cannot be opened,
    which would indicate a setup problem worth surfacing to the user.
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get the most recent rate timestamp across all pairs
        cursor.execute("""
            SELECT MAX(timestamp) AS last_fetch FROM rates
        """)
        last_fetch_row = cursor.fetchone()
        last_fetch = last_fetch_row["last_fetch"] if last_fetch_row else None

        # Count active alerts
        cursor.execute("SELECT COUNT(*) AS cnt FROM alert_thresholds")
        alert_count = cursor.fetchone()["cnt"]

        conn.close()

        return jsonify({
            "db_connected":  True,
            "db_path":       DATABASE_FILE,
            "last_fetch":    last_fetch,
            "alert_count":   alert_count,
            "tracked_pairs": len(PAIR_STRINGS),
        }), 200

    except Exception as e:
        # Return a partial response so the dashboard status bar still renders
        return jsonify({
            "db_connected":  False,
            "db_path":       DATABASE_FILE,
            "last_fetch":    None,
            "alert_count":   0,
            "tracked_pairs": len(PAIR_STRINGS),
            "error":         str(e),
        }), 200


# ── Entry point ───────────────────────────────────────────────────────────────
@app.route("/")
def serve_dashboard():
    """Serve the dashboard HTML file from the finflow directory."""
    import os
    dashboard_dir = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(dashboard_dir, "dashboard.html")
if __name__ == "__main__":
    # debug=False for local use — debug mode auto-reloads on file changes
    # which can cause the database to be initialised twice on startup
    app.run(host="127.0.0.1", port=API_PORT, debug=False)
