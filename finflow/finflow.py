"""
FinFlow - Command-line FX rate tracker.
Main entry point for the application.
"""

import argparse
import sys
from fetcher import fetch_rate
from storage import store_rate, get_history, init_database
from alerts import set_threshold, get_threshold, check_alert, print_alert
from config import DEFAULT_FROM_CURRENCY, DEFAULT_TO_CURRENCY


def cmd_fetch(args) -> None:
    """
    Fetch and store the current exchange rate.
    
    Args:
        args: Parsed command line arguments
    """
    try:
        # Fetch the current rate from the API
        rate = fetch_rate(args.from_currency, args.to_currency)
        
        # Store the rate in the database
        store_rate(args.from_currency, args.to_currency, rate)
        
        # Display the fetched rate
        print(f"✓ {args.from_currency}/{args.to_currency}: {rate:.4f}")
        
        # Check for any threshold breaches
        alert = check_alert(args.from_currency, args.to_currency, rate)
        print_alert(alert)
        
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_history(args) -> None:
    """
    Display rate history for a currency pair.
    
    Args:
        args: Parsed command line arguments
    """
    # Get historical rates from the database
    history = get_history(args.from_currency, args.to_currency, limit=args.limit)
    
    if not history:
        print(f"No history found for {args.from_currency}/{args.to_currency}")
        return
    
    # Print header
    print(f"\nRate History: {args.from_currency}/{args.to_currency}")
    print("-" * 50)
    print(f"{'ID':<6} {'Rate':<12} {'Timestamp'}")
    print("-" * 50)
    
    # Print each historical rate
    for row_id, rate, timestamp in history:
        print(f"{row_id:<6} {rate:<12.4f} {timestamp}")
    
    print("-" * 50)
    print(f"Total: {len(history)} records\n")


def cmd_alert(args) -> None:
    """
    Set or view alert thresholds for a currency pair.
    
    Args:
        args: Parsed command line arguments
    """
    # If no thresholds provided, display current settings
    if args.low is None and args.high is None:
        thresholds = get_threshold(args.from_currency, args.to_currency)
        
        if thresholds is None:
            print(f"No thresholds set for {args.from_currency}/{args.to_currency}")
        else:
            low, high = thresholds
            print(f"\nThresholds for {args.from_currency}/{args.to_currency}:")
            print(f"  Low:  {low if low else 'Not set'}")
            print(f"  High: {high if high else 'Not set'}\n")
        return
    
    try:
        # Set the new thresholds
        set_threshold(args.from_currency, args.to_currency, args.low, args.high)
        print(f"✓ Alert thresholds set for {args.from_currency}/{args.to_currency}")
        
        if args.low:
            print(f"  Low threshold:  {args.low:.4f}")
        if args.high:
            print(f"  High threshold: {args.high:.4f}")
            
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser.
    
    Returns:
        Configured ArgumentParser instance
    """
    # Create main parser
    parser = argparse.ArgumentParser(
        prog="finflow",
        description="FinFlow - Command-line FX rate tracker"
    )
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Fetch command
    fetch_parser = subparsers.add_parser("fetch", help="Fetch current exchange rate")
    fetch_parser.add_argument(
        "-f", "--from", dest="from_currency",
        default=DEFAULT_FROM_CURRENCY,
        help=f"Base currency (default: {DEFAULT_FROM_CURRENCY})"
    )
    fetch_parser.add_argument(
        "-t", "--to", dest="to_currency",
        default=DEFAULT_TO_CURRENCY,
        help=f"Target currency (default: {DEFAULT_TO_CURRENCY})"
    )
    fetch_parser.set_defaults(func=cmd_fetch)
    
    # History command
    history_parser = subparsers.add_parser("history", help="Show rate history")
    history_parser.add_argument(
        "-f", "--from", dest="from_currency",
        default=DEFAULT_FROM_CURRENCY,
        help=f"Base currency (default: {DEFAULT_FROM_CURRENCY})"
    )
    history_parser.add_argument(
        "-t", "--to", dest="to_currency",
        default=DEFAULT_TO_CURRENCY,
        help=f"Target currency (default: {DEFAULT_TO_CURRENCY})"
    )
    history_parser.add_argument(
        "-l", "--limit", type=int, default=10,
        help="Maximum number of records to show (default: 10)"
    )
    history_parser.set_defaults(func=cmd_history)
    
    # Alert command
    alert_parser = subparsers.add_parser("alert", help="Set or view alert thresholds")
    alert_parser.add_argument(
        "-f", "--from", dest="from_currency",
        default=DEFAULT_FROM_CURRENCY,
        help=f"Base currency (default: {DEFAULT_FROM_CURRENCY})"
    )
    alert_parser.add_argument(
        "-t", "--to", dest="to_currency",
        default=DEFAULT_TO_CURRENCY,
        help=f"Target currency (default: {DEFAULT_TO_CURRENCY})"
    )
    alert_parser.add_argument(
        "--low", type=float,
        help="Low threshold - alert when rate falls below this"
    )
    alert_parser.add_argument(
        "--high", type=float,
        help="High threshold - alert when rate rises above this"
    )
    alert_parser.set_defaults(func=cmd_alert)
    
    return parser


def main() -> None:
    """
    Main entry point for the FinFlow application.
    """
    # Initialize the database
    init_database()
    
    # Parse command line arguments
    parser = create_parser()
    args = parser.parse_args()
    
    # Check if a command was provided
    if args.command is None:
        parser.print_help()
        sys.exit(0)
    
    # Execute the appropriate command function
    args.func(args)


if __name__ == "__main__":
    main()