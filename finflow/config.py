"""
Configuration module for FinFlow FX rate tracker.
Contains API endpoints and database settings.
"""

# Base URL for the Frankfurter API
API_BASE_URL = "https://api.frankfurter.app"

# Default endpoint for fetching latest rates
LATEST_ENDPOINT = "/latest"

# Default database file name
DATABASE_FILE = "finflow.db"

# Default currency pair
DEFAULT_FROM_CURRENCY = "GBP"
DEFAULT_TO_CURRENCY = "USD"

# Request timeout in seconds
REQUEST_TIMEOUT = 10