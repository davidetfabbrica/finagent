"""
Test suite for FinFlow FX rate tracker.
Uses pytest and unittest.mock for offline testing.
"""

import pytest
import os
import tempfile
from unittest.mock import patch, Mock
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fetcher import fetch_rate
from storage import store_rate, get_history, init_database
from alerts import set_threshold, check_alert, get_threshold


# Fixture for temporary database
@pytest.fixture
def temp_db():
    """
    Create a temporary database file for testing.
    Yields the path and cleans up after the test.
    """
    # Create a temporary file for the test database
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    # Initialize the database
    init_database(path)
    
    yield path
    
    # Cleanup after test
    if os.path.exists(path):
        os.unlink(path)


# Mock response data for the Frankfurter API
MOCK_RESPONSE_GBP_USD = {
    "amount": 1.0,
    "base": "GBP",
    "date": "2024-01-15",
    "rates": {
        "USD": 1.2750
    }
}


class MockResponse:
    """Mock HTTP response class for testing."""
    
    def __init__(self, json_data, status_code=200):
        """Initialize mock response with data and status code."""
        self.json_data = json_data
        self.status_code = status_code
    
    def json(self):
        """Return the mock JSON data."""
        return self.json_data
    
    def raise_for_status(self):
        """Raise an exception for error status codes."""
        if self.status_code >= 400:
            from requests.exceptions import HTTPError
            raise HTTPError(f"HTTP Error: {self.status_code}")


def test_fetch_rate_returns_float():
    """
    Test 1: fetch_rate() returns a float for a valid pair.
    Mocks the HTTP call to return a valid response.
    """
    # Create a mock response with valid rate data
    mock_response = MockResponse(MOCK_RESPONSE_GBP_USD, 200)
    
    # Patch the requests.get function to return our mock
    with patch("fetcher.requests.get", return_value=mock_response):
        # Call fetch_rate and verify the result
        rate = fetch_rate("GBP", "USD")
        
        # Assert that the result is a float
        assert isinstance(rate, float), "fetch_rate should return a float"
        
        # Assert the rate matches our mock data
        assert rate == 1.2750, "Rate should match mock data"


def test_fetched_rate_stored_in_database(temp_db):
    """
    Test 2: A fetched rate is written to the database correctly.
    Verifies that store_rate properly saves data.
    """
    # Create mock response
    mock_response = MockResponse(MOCK_RESPONSE_GBP_USD, 200)
    
    with patch("fetcher.requests.get", return_value=mock_response):
        # Fetch the rate
        rate = fetch_rate("GBP", "USD")
        
        # Store the rate in the database
        row_id = store_rate("GBP", "USD", rate, db_path=temp_db)
        
        # Verify the row was inserted
        assert row_id is not None, "store_rate should return a row ID"
        assert row_id > 0, "Row ID should be positive"
        
        # Retrieve the history and verify the stored data
        history = get_history("GBP", "USD", db_path=temp_db)
        
        assert len(history) > 0, "History should contain at least one record"
        
        # Check the stored rate matches
        stored_rate = history[0][1]
        assert stored_rate == rate, "Stored rate should match fetched rate"


def test_rate_below_threshold_triggers_alert(temp_db):
    """
    Test 3: A rate below threshold triggers an alert.
    Sets a low threshold and verifies alert is triggered.
    """
    # Set a low threshold at 1.30
    set_threshold("GBP", "USD", threshold_low=1.30, db_path=temp_db)
    
    # Check with a rate below the threshold (1.25)
    current_rate = 1.25
    alert = check_alert("GBP", "USD", current_rate, db_path=temp_db)
    
    # Verify an alert was triggered
    assert alert is not None, "Alert should be triggered when rate is below threshold"
    assert "BELOW" in alert, "Alert message should indicate rate is below threshold"
    assert "1.25" in alert or "1.2500" in alert, "Alert should contain the current rate"


def test_rate_above_threshold_no_alert(temp_db):
    """
    Test 4: A rate above threshold does not trigger an alert.
    Sets thresholds and verifies no alert for normal rates.
    """
    # Set thresholds: low=1.20, high=1.40
    set_threshold("GBP", "USD", threshold_low=1.20, threshold_high=1.40, db_path=temp_db)
    
    # Check with a rate within the normal range (1.30)
    current_rate = 1.30
    alert = check_alert("GBP", "USD", current_rate, db_path=temp_db)
    
    # Verify no alert was triggered
    assert alert is None, "No alert should be triggered for rate within thresholds"


def test_invalid_pair_raises_error():
    """
    Test 5: An invalid pair raises a clear error.
    Tests that invalid currency codes result in ValueError.
    """
    # Create a mock response for invalid pair (404 error)
    mock_response = MockResponse({}, 404)
    
    with patch("fetcher.requests.get", return_value=mock_response):
        # Attempt to fetch an invalid pair and expect ValueError
        with pytest.raises(ValueError) as excinfo:
            fetch_rate("XXX", "YYY")
        
        # Verify the error message is clear
        assert "Invalid currency pair" in str(excinfo.value), \
            "Error message should indicate invalid currency pair"


def test_history_returns_rows_after_fetch(temp_db):
    """
    Test 6: history() returns at least one row after a fetch.
    Verifies complete flow from fetch to history retrieval.
    """
    # Create mock response
    mock_response = MockResponse(MOCK_RESPONSE_GBP_USD, 200)
    
    with patch("fetcher.requests.get", return_value=mock_response):
        # Fetch and store a rate
        rate = fetch_rate("GBP", "USD")
        store_rate("GBP", "USD", rate, db_path=temp_db)
        
        # Retrieve history
        history = get_history("GBP", "USD", db_path=temp_db)
        
        # Verify at least one row is returned
        assert len(history) >= 1, "History should return at least one row after fetch"
        
        # Verify the row structure (id, rate, timestamp)
        row = history[0]
        assert len(row) == 3, "Each history row should have 3 fields"
        assert isinstance(row[0], int), "First field should be ID (int)"
        assert isinstance(row[1], float), "Second field should be rate (float)"
        assert row[2] is not None, "Third field should be timestamp"


def test_empty_currency_raises_error():
    """
    Additional test: Empty currency codes raise ValueError.
    """
    # Test with empty from_currency
    with pytest.raises(ValueError) as excinfo:
        fetch_rate("", "USD")
    
    assert "empty" in str(excinfo.value).lower(), \
        "Error should indicate empty currency"


def test_threshold_high_alert(temp_db):
    """
    Additional test: Rate above high threshold triggers alert.
    """
    # Set a high threshold at 1.25
    set_threshold("GBP", "USD", threshold_high=1.25, db_path=temp_db)
    
    # Check with a rate above the threshold (1.30)
    current_rate = 1.30
    alert = check_alert("GBP", "USD", current_rate, db_path=temp_db)
    
    # Verify an alert was triggered
    assert alert is not None, "Alert should be triggered when rate is above threshold"
    assert "ABOVE" in alert, "Alert message should indicate rate is above threshold"


def test_store_rate_validates_input(temp_db):
    """
    Additional test: store_rate validates rate input.
    """
    # Test with invalid rate (negative)
    with pytest.raises(ValueError):
        store_rate("GBP", "USD", -1.5, db_path=temp_db)
    
    # Test with zero rate
    with pytest.raises(ValueError):
        store_rate("GBP", "USD", 0, db_path=temp_db)


def test_set_threshold_validation(temp_db):
    """
    Additional test: set_threshold validates threshold values.
    """
    # Test with both thresholds as None
    with pytest.raises(ValueError) as excinfo:
        set_threshold("GBP", "USD", db_path=temp_db)
    
    assert "at least one threshold" in str(excinfo.value).lower()
    
    # Test with low >= high
    with pytest.raises(ValueError):
        set_threshold("GBP", "USD", threshold_low=1.5, threshold_high=1.3, db_path=temp_db)