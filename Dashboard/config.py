"""
Configuration module for FinFlow FX rate tracker.
Contains API endpoints, database settings, and tracked currency pairs.
"""

import os

# Base URL for the Frankfurter API
API_BASE_URL = "https://api.frankfurter.app"

# Default endpoint for fetching latest rates
LATEST_ENDPOINT = "/latest"

# Resolve the database path relative to this config file, not the working
# directory. This means finflow.db always lives next to the source files,
# regardless of where you run the script from.
_HERE = os.path.dirname(os.path.abspath(__file__))
DATABASE_FILE = os.path.join(_HERE, "finflow.db")

# Default currency pair (used by the CLI if no pair is specified)
DEFAULT_FROM_CURRENCY = "GBP"
DEFAULT_TO_CURRENCY = "USD"

# All GBP pairs tracked by the dashboard.
# Each entry is a (from, to) tuple. The base is always GBP.
GBP_PAIRS = [
    ("GBP", "USD"),
    ("GBP", "EUR"),
    ("GBP", "JPY"),
    ("GBP", "CHF"),
    ("GBP", "CAD"),
    ("GBP", "AUD"),
    ("GBP", "CNY"),
]

# Convenience list of pair strings in "GBP/USD" format, used by the API layer
PAIR_STRINGS = [f"{f}/{t}" for f, t in GBP_PAIRS]

# How many days of rate history to keep and serve
HISTORY_DAYS = 180

# Request timeout in seconds for calls to the Frankfurter API
REQUEST_TIMEOUT = 10

# Port the Flask dashboard API runs on.
# 5001 avoids conflict with macOS AirPlay Receiver which occupies port 5000.
API_PORT = 5001
