"""
Fetcher module for retrieving live FX rates from the Frankfurter API.
"""

import requests
from config import API_BASE_URL, LATEST_ENDPOINT, REQUEST_TIMEOUT


def fetch_rate(from_currency: str, to_currency: str) -> float:
    """
    Fetch the current exchange rate for a currency pair.
    
    Args:
        from_currency: The base currency code (e.g., 'GBP')
        to_currency: The target currency code (e.g., 'USD')
    
    Returns:
        The current exchange rate as a float
    
    Raises:
        ValueError: If the currency pair is invalid
        RuntimeError: If the API request fails
    """
    # Validate input currencies are not empty
    if not from_currency or not to_currency:
        raise ValueError("Currency codes cannot be empty")
    
    # Convert to uppercase for consistency
    from_currency = from_currency.upper().strip()
    to_currency = to_currency.upper().strip()
    
    # Construct the API URL with query parameters
    url = f"{API_BASE_URL}{LATEST_ENDPOINT}"
    params = {
        "from": from_currency,
        "to": to_currency
    }
    
    try:
        # Make the HTTP GET request to the API
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        
        # Check for HTTP errors
        if response.status_code == 404:
            raise ValueError(f"Invalid currency pair: {from_currency}/{to_currency}")
        
        response.raise_for_status()
        
        # Parse the JSON response
        data = response.json()
        
        # Extract the rate from the response
        rates = data.get("rates", {})
        
        if to_currency not in rates:
            raise ValueError(f"Invalid currency pair: {from_currency}/{to_currency}")
        
        # Return the exchange rate as a float
        rate = float(rates[to_currency])
        return rate
        
    except requests.exceptions.Timeout:
        raise RuntimeError("API request timed out")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Failed to connect to the API")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"API request failed: {str(e)}")


def validate_currency_pair(from_currency: str, to_currency: str) -> bool:
    """
    Validate if a currency pair is supported by the API.
    
    Args:
        from_currency: The base currency code
        to_currency: The target currency code
    
    Returns:
        True if the pair is valid, False otherwise
    """
    try:
        # Attempt to fetch the rate to validate the pair
        fetch_rate(from_currency, to_currency)
        return True
    except (ValueError, RuntimeError):
        return False