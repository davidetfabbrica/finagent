"""
Storage module for persisting FX rates in a SQLite database.

Existing functions (init_database, store_rate, get_history, get_latest_rate)
are unchanged from the original FinFlow CLI implementation.

New functions added for the dashboard:
  - get_rate_history()     : returns time-series data for sparkline charts
  - get_all_latest_rates() : returns current + previous rate for all pairs
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict
from config import DATABASE_FILE, GBP_PAIRS, HISTORY_DAYS


def init_database(db_path: str = DATABASE_FILE) -> None:
    """
    Initialize the SQLite database with required tables.
    Creates the file if it does not exist. Safe to call multiple times.

    Args:
        db_path: Path to the SQLite database file
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Stores every fetched rate with a timestamp — this is the core time series
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rates (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            from_currency TEXT NOT NULL,
            to_currency   TEXT NOT NULL,
            rate          REAL NOT NULL,
            timestamp     DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Stores user-defined alert thresholds per pair
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alert_thresholds (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            from_currency TEXT NOT NULL,
            to_currency   TEXT NOT NULL,
            threshold_low  REAL,
            threshold_high REAL,
            UNIQUE(from_currency, to_currency)
        )
    """)

    conn.commit()
    conn.close()


def store_rate(from_currency: str, to_currency: str, rate: float,
               db_path: str = DATABASE_FILE) -> int:
    """
    Store an exchange rate in the database.

    Args:
        from_currency: Base currency code (e.g. 'GBP')
        to_currency:   Target currency code (e.g. 'USD')
        rate:          The exchange rate value — must be a positive number
        db_path:       Path to the database file

    Returns:
        The row ID of the inserted record

    Raises:
        ValueError: If the rate is not a valid positive number
    """
    if not isinstance(rate, (int, float)) or rate <= 0:
        raise ValueError(f"Invalid rate value: {rate}")

    init_database(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO rates (from_currency, to_currency, rate, timestamp)
        VALUES (?, ?, ?, ?)
    """, (from_currency.upper(), to_currency.upper(), rate, datetime.now().isoformat()))

    row_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return row_id


def get_history(from_currency: str, to_currency: str,
                limit: int = 100, db_path: str = DATABASE_FILE) -> List[Tuple]:
    """
    Retrieve rate history for a currency pair (CLI use).
    Returns records newest-first, up to the given limit.

    Args:
        from_currency: Base currency code
        to_currency:   Target currency code
        limit:         Maximum number of records to return
        db_path:       Path to the database file

    Returns:
        List of (id, rate, timestamp) tuples, newest first
    """
    init_database(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, rate, timestamp
        FROM rates
        WHERE from_currency = ? AND to_currency = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (from_currency.upper(), to_currency.upper(), limit))

    results = cursor.fetchall()
    conn.close()

    return results


def get_latest_rate(from_currency: str, to_currency: str,
                    db_path: str = DATABASE_FILE) -> Optional[Tuple]:
    """
    Get the most recent stored rate for a currency pair.

    Args:
        from_currency: Base currency code
        to_currency:   Target currency code
        db_path:       Path to the database file

    Returns:
        (rate, timestamp) tuple, or None if no data exists
    """
    history = get_history(from_currency, to_currency, limit=1, db_path=db_path)

    if history:
        return (history[0][1], history[0][2])

    return None


# ── New functions for the dashboard ──────────────────────────────────────────

def get_rate_history(pair: str, days: int = HISTORY_DAYS,
                     db_path: str = DATABASE_FILE) -> List[Dict]:
    """
    Return time-series rate data for a single pair, for use in sparkline charts.

    Queries the existing 'rates' table — no schema changes required.
    Returns records oldest-first so the chart reads left-to-right chronologically.
    Rows older than 'days' days are excluded.

    Args:
        pair:    Currency pair string in "GBP/USD" format
        days:    How many days of history to return (default: 180)
        db_path: Path to the database file

    Returns:
        List of dicts: [{"timestamp": str, "rate": float}, ...]
        Empty list if pair is unknown or has no data.

    Raises:
        ValueError: If the pair string is not in "AAA/BBB" format
    """
    # Validate and split the pair string
    if "/" not in pair:
        raise ValueError(f"Pair must be in 'GBP/USD' format, got: {pair}")

    from_currency, to_currency = pair.upper().split("/", 1)

    # Calculate the cutoff date — anything older than this is excluded
    cutoff = datetime.now() - timedelta(days=days)

    init_database(db_path)

    conn = sqlite3.connect(db_path)
    # row_factory makes rows behave like dicts, which is cleaner to work with
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT rate, timestamp
        FROM rates
        WHERE from_currency = ?
          AND to_currency   = ?
          AND timestamp     >= ?
        ORDER BY timestamp ASC
    """, (from_currency, to_currency, cutoff.isoformat()))

    rows = cursor.fetchall()
    conn.close()

    # Convert Row objects to plain dicts for easy JSON serialisation
    return [{"timestamp": row["timestamp"], "rate": row["rate"]} for row in rows]


def get_all_latest_rates(db_path: str = DATABASE_FILE) -> List[Dict]:
    """
    Return the current and previous rate for every tracked GBP pair.

    Used by the /api/rates endpoint to populate all dashboard cards in one call.
    The 24-hour change percentage is calculated from the two most recent rows
    per pair, so the caller does not need to do any arithmetic.

    Args:
        db_path: Path to the database file

    Returns:
        List of dicts, one per pair:
        [
          {
            "pair":       "GBP/USD",
            "rate":       1.3165,        # most recent stored rate
            "previous":   1.3120,        # second most recent stored rate
            "change_pct": 0.34,          # percentage change, 2 decimal places
            "timestamp":  "2026-06-07 19:02:27"
          },
          ...
        ]
        If a pair has no data, it is included with rate/previous/change_pct as None.
    """
    init_database(db_path)

    results = []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    for from_currency, to_currency in GBP_PAIRS:
        pair_string = f"{from_currency}/{to_currency}"

        # Fetch the two most recent rows for this pair
        cursor.execute("""
            SELECT rate, timestamp
            FROM rates
            WHERE from_currency = ? AND to_currency = ?
            ORDER BY timestamp DESC
            LIMIT 2
        """, (from_currency, to_currency))

        rows = cursor.fetchall()

        if not rows:
            # No data yet for this pair — return nulls so the dashboard can
            # show a placeholder rather than crashing
            results.append({
                "pair":       pair_string,
                "rate":       None,
                "previous":   None,
                "change_pct": None,
                "timestamp":  None,
            })
            continue

        current_rate  = rows[0]["rate"]
        current_ts    = rows[0]["timestamp"]
        previous_rate = rows[1]["rate"] if len(rows) > 1 else None

        # Calculate percentage change, avoiding division by zero
        if previous_rate and previous_rate != 0:
            change_pct = round(((current_rate - previous_rate) / previous_rate) * 100, 2)
        else:
            change_pct = None

        results.append({
            "pair":       pair_string,
            "rate":       current_rate,
            "previous":   previous_rate,
            "change_pct": change_pct,
            "timestamp":  current_ts,
        })

    conn.close()
    return results
