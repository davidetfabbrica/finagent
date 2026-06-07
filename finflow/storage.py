"""
Storage module for persisting FX rates in a SQLite database.
"""

import sqlite3
from datetime import datetime
from typing import List, Tuple, Optional
from config import DATABASE_FILE


def init_database(db_path: str = DATABASE_FILE) -> None:
    """
    Initialize the SQLite database with required tables.
    
    Args:
        db_path: Path to the database file
    """
    # Connect to the database (creates file if it doesn't exist)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create the rates table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_currency TEXT NOT NULL,
            to_currency TEXT NOT NULL,
            rate REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create the alerts table for storing user-defined thresholds
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alert_thresholds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_currency TEXT NOT NULL,
            to_currency TEXT NOT NULL,
            threshold_low REAL,
            threshold_high REAL,
            UNIQUE(from_currency, to_currency)
        )
    """)
    
    # Commit changes and close connection
    conn.commit()
    conn.close()


def store_rate(from_currency: str, to_currency: str, rate: float, 
               db_path: str = DATABASE_FILE) -> int:
    """
    Store an exchange rate in the database.
    
    Args:
        from_currency: The base currency code
        to_currency: The target currency code
        rate: The exchange rate value
        db_path: Path to the database file
    
    Returns:
        The ID of the inserted row
    
    Raises:
        ValueError: If rate is not a valid number
    """
    # Validate the rate is a valid number
    if not isinstance(rate, (int, float)) or rate <= 0:
        raise ValueError(f"Invalid rate value: {rate}")
    
    # Ensure database is initialized
    init_database(db_path)
    
    # Connect and insert the rate
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Insert the rate with current timestamp
    cursor.execute("""
        INSERT INTO rates (from_currency, to_currency, rate, timestamp)
        VALUES (?, ?, ?, ?)
    """, (from_currency.upper(), to_currency.upper(), rate, datetime.now()))
    
    # Get the ID of the inserted row
    row_id = cursor.lastrowid
    
    # Commit and close
    conn.commit()
    conn.close()
    
    return row_id


def get_history(from_currency: str, to_currency: str, 
                limit: int = 100, db_path: str = DATABASE_FILE) -> List[Tuple]:
    """
    Retrieve rate history for a currency pair.
    
    Args:
        from_currency: The base currency code
        to_currency: The target currency code
        limit: Maximum number of records to return
        db_path: Path to the database file
    
    Returns:
        List of tuples containing (id, rate, timestamp)
    """
    # Ensure database is initialized
    init_database(db_path)
    
    # Connect and query
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Fetch historical rates ordered by timestamp descending
    cursor.execute("""
        SELECT id, rate, timestamp
        FROM rates
        WHERE from_currency = ? AND to_currency = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (from_currency.upper(), to_currency.upper(), limit))
    
    # Fetch all results
    results = cursor.fetchall()
    
    # Close connection
    conn.close()
    
    return results


def get_latest_rate(from_currency: str, to_currency: str,
                    db_path: str = DATABASE_FILE) -> Optional[Tuple]:
    """
    Get the most recent stored rate for a currency pair.
    
    Args:
        from_currency: The base currency code
        to_currency: The target currency code
        db_path: Path to the database file
    
    Returns:
        Tuple of (rate, timestamp) or None if no data exists
    """
    # Get history with limit of 1
    history = get_history(from_currency, to_currency, limit=1, db_path=db_path)
    
    if history:
        # Return rate and timestamp from the first result
        return (history[0][1], history[0][2])
    
    return None