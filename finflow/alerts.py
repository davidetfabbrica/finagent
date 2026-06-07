"""
Alerts module for managing and checking FX rate thresholds.
"""

import sqlite3
from typing import Optional, Tuple
from config import DATABASE_FILE
from storage import init_database


def set_threshold(from_currency: str, to_currency: str,
                  threshold_low: Optional[float] = None,
                  threshold_high: Optional[float] = None,
                  db_path: str = DATABASE_FILE) -> None:
    """
    Set alert thresholds for a currency pair.
    
    Args:
        from_currency: The base currency code
        to_currency: The target currency code
        threshold_low: Alert when rate falls below this value
        threshold_high: Alert when rate rises above this value
        db_path: Path to the database file
    
    Raises:
        ValueError: If both thresholds are None or invalid
    """
    # Validate that at least one threshold is provided
    if threshold_low is None and threshold_high is None:
        raise ValueError("At least one threshold (low or high) must be provided")
    
    # Validate threshold values are positive if provided
    if threshold_low is not None and threshold_low <= 0:
        raise ValueError(f"Low threshold must be positive: {threshold_low}")
    
    if threshold_high is not None and threshold_high <= 0:
        raise ValueError(f"High threshold must be positive: {threshold_high}")
    
    # Validate low is less than high if both are provided
    if threshold_low is not None and threshold_high is not None:
        if threshold_low >= threshold_high:
            raise ValueError("Low threshold must be less than high threshold")
    
    # Ensure database is initialized
    init_database(db_path)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Insert or replace the threshold settings
    cursor.execute("""
        INSERT OR REPLACE INTO alert_thresholds 
        (from_currency, to_currency, threshold_low, threshold_high)
        VALUES (?, ?, ?, ?)
    """, (from_currency.upper(), to_currency.upper(), threshold_low, threshold_high))
    
    # Commit and close
    conn.commit()
    conn.close()


def get_threshold(from_currency: str, to_currency: str,
                  db_path: str = DATABASE_FILE) -> Optional[Tuple[float, float]]:
    """
    Get the current threshold settings for a currency pair.
    
    Args:
        from_currency: The base currency code
        to_currency: The target currency code
        db_path: Path to the database file
    
    Returns:
        Tuple of (threshold_low, threshold_high) or None if not set
    """
    # Ensure database is initialized
    init_database(db_path)
    
    # Connect and query
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Fetch threshold settings
    cursor.execute("""
        SELECT threshold_low, threshold_high
        FROM alert_thresholds
        WHERE from_currency = ? AND to_currency = ?
    """, (from_currency.upper(), to_currency.upper()))
    
    result = cursor.fetchone()
    conn.close()
    
    return result


def check_alert(from_currency: str, to_currency: str, current_rate: float,
                db_path: str = DATABASE_FILE) -> Optional[str]:
    """
    Check if the current rate breaches any threshold.
    
    Args:
        from_currency: The base currency code
        to_currency: The target currency code
        current_rate: The current exchange rate
        db_path: Path to the database file
    
    Returns:
        Alert message string if threshold breached, None otherwise
    """
    # Get the threshold settings for this pair
    thresholds = get_threshold(from_currency, to_currency, db_path)
    
    if thresholds is None:
        # No thresholds set for this pair
        return None
    
    threshold_low, threshold_high = thresholds
    
    # Check if rate is below low threshold
    if threshold_low is not None and current_rate < threshold_low:
        return (f"⚠️  ALERT: {from_currency}/{to_currency} rate ({current_rate:.4f}) "
                f"is BELOW threshold ({threshold_low:.4f})")
    
    # Check if rate is above high threshold
    if threshold_high is not None and current_rate > threshold_high:
        return (f"⚠️  ALERT: {from_currency}/{to_currency} rate ({current_rate:.4f}) "
                f"is ABOVE threshold ({threshold_high:.4f})")
    
    # No threshold breached
    return None


def print_alert(alert_message: Optional[str]) -> bool:
    """
    Print an alert message to the terminal if one exists.
    
    Args:
        alert_message: The alert message to print
    
    Returns:
        True if an alert was printed, False otherwise
    """
    if alert_message:
        # Print the alert with visual emphasis
        print("\n" + "=" * 60)
        print(alert_message)
        print("=" * 60 + "\n")
        return True
    
    return False