#!/usr/bin/env python3
"""
Kalshi Event Drill-Down Tool - Deep Analysis of Individual Events

PURPOSE:
    Bridge the gap between discovery (platform_snapshot.py) and execution.
    Provides detailed view of ALL markets within a specific event to understand
    the full probability distribution before placing trades.

WHAT IT DOES:
    - Takes an event ticker as input (e.g., FED-26JAN29, INXD-26JAN24)
    - Displays ALL markets within that event in a readable table
    - Shows each market's strike/outcome, current YES price, volume, spread
    - Identifies if event is mutually exclusive (for arbitrage analysis)
    - Calculates sum of probabilities (flags arb opportunities when sum != $1.00)

VALUE:
    - Understand the full probability distribution traders expect
    - See all betting options before placing a trade
    - Foundation for Range Bets, Spreads, and Arbitrage strategies
    - Essential tool for informed decision-making

USAGE EXAMPLES:

    BASIC USAGE:
    ------------
    # Drill down into a specific event
    python event_drilldown.py FED-26JAN29

    # Get event details with full market info
    python event_drilldown.py INXD-26JAN24

    SORTING OPTIONS:
    ----------------
    # Sort by price (default - see probability distribution)
    python event_drilldown.py FED-26JAN29 --sort price

    # Sort by volume (most liquid markets first)
    python event_drilldown.py FED-26JAN29 --sort volume

    # Sort by strike/outcome name
    python event_drilldown.py FED-26JAN29 --sort strike

    # Sort by spread (tightest spreads first)
    python event_drilldown.py FED-26JAN29 --sort spread

    DATA EXPORT:
    ------------
    # Export to JSON for analysis
    python event_drilldown.py FED-26JAN29 --output-format json -o event.json

    # Export to CSV for spreadsheet
    python event_drilldown.py FED-26JAN29 --output-format csv -o event.csv

FULL PARAMETER REFERENCE:
    EVENT_TICKER          The event ticker to analyze (required)
                          Example: FED-26JAN29, INXD-26JAN24, CPI-26FEB14

    --sort MODE           Sort order for markets (default: price)
                          Options:
                            price: Highest YES price first (probability ranking)
                            volume: Most liquid markets first
                            strike: Alphabetical by outcome/strike
                            spread: Tightest bid-ask spread first

    --output-format FMT   Output format (default: console)
                          Options: console, json, csv

    --output-file PATH    Save output to file instead of stdout
    -o PATH              (short form)

API ENDPOINT USED:
    GET /events/{ticker}  - Event details with nested markets
                           Using with_nested_markets=true

    This is a public endpoint (no authentication required)

INSTALLATION:
    pip install requests rich

UNDERSTANDING THE OUTPUT:

    Event Header:
    - Title: Full event name
    - Ticker: Event identifier (use this with platform_snapshot.py)
    - Category: Market category (Economics, Politics, etc.)
    - Series: Parent series this event belongs to
    - Status: open, closed, or settled
    - Mutually Exclusive: YES if only one outcome can win (important for arb)

    Markets Table Columns:
    - #: Row number
    - Market/Outcome: The specific outcome being traded (e.g., "450-474 bps", "Yes", "No")
    - Ticker: Market ticker for order placement
    - YES: Current YES price in cents
    - NO: Implied NO price (100 - YES)
    - Bid: Best bid price
    - Ask: Best ask price
    - Spread: Bid-ask spread in cents (lower = more efficient)
    - Volume: Total historical volume
    - Vol 24h: Volume in last 24 hours
    - Open Int: Current open interest (active positions)
    - Close: Time until market closes

    Analysis Section (for mutually exclusive events):
    - Sum of YES prices: Should equal ~$1.00 for efficient markets
    - If sum < $1.00: Potential BUY arbitrage (buy all outcomes)
    - If sum > $1.00: Potential SELL arbitrage (sell all outcomes)
    - Shows potential profit/loss before fees

TRADING STRATEGIES SUPPORTED:

    Strategy 1: Certainty Gap Analysis
        See which outcomes are priced 90-97¢ and have room to run to 99¢

    Strategy 5: Range Bets
        Identify strike prices for two-leg structures (buy YES on lower, NO on upper)

    Strategy 6: Sum-of-Probabilities Arbitrage
        When mutually_exclusive=true and sum != $1.00, potential arb exists

    Strategy 7: Spread Analysis
        Focus on markets with tight spreads (<2¢) where your edge isn't eaten

NEXT STEPS AFTER DRILL-DOWN:
    1. Identify which market(s) to trade based on your thesis
    2. Check order book depth: GET /market/{ticker}/orderbook (requires auth)
    3. Review market rules and settlement sources on Kalshi website
    4. Place trades manually or build automation
"""

import argparse
import json
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    print("Error: 'requests' library required. Install with: pip install requests")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Warning: 'rich' library not found. Install for better formatting: pip install rich",
          file=sys.stderr)


# API Configuration
BASE_URL = "https://api.elections.kalshi.com/trade-api/v2/"


class KalshiEventDrilldown:
    """Client for fetching and analyzing individual Kalshi events."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'Kalshi-Event-Drilldown/1.0'
        })

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request to API endpoint."""
        url = urljoin(self.base_url, endpoint)
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"Error: Event not found. Check that '{endpoint.split('/')[-1]}' is a valid event ticker.",
                      file=sys.stderr)
            else:
                print(f"Error fetching {endpoint}: {e}", file=sys.stderr)
            raise
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {endpoint}: {e}", file=sys.stderr)
            raise

    def get_event(self, event_ticker: str) -> Dict[str, Any]:
        """Fetch detailed event data with all nested markets."""
        print(f"Fetching event: {event_ticker}...", file=sys.stderr)
        params = {'with_nested_markets': 'true'}
        data = self._get(f'events/{event_ticker}', params=params)
        event = data.get('event', {})
        markets = event.get('markets', [])
        print(f"Found {len(markets)} markets in this event", file=sys.stderr)
        return event

    def analyze_event(self, event: Dict[str, Any], sort_by: str = 'price') -> Dict[str, Any]:
        """
        Analyze event data and enrich markets with calculated metrics.

        Args:
            event: Event data from API
            sort_by: Sort method (price, volume, strike, spread)

        Returns:
            Dictionary with enriched event analysis
        """
        print("Analyzing event...", file=sys.stderr)
        markets = event.get('markets', [])

        # Enrich each market with calculated metrics
        enriched_markets = []
        for market in markets:
            enriched = dict(market)

            # Get YES price (cents)
            yes_price_str = market.get('last_price_dollars') or market.get('yes_bid_dollars', '0')
            try:
                enriched['yes_price_cents'] = int(float(yes_price_str) * 100)
            except (ValueError, TypeError):
                enriched['yes_price_cents'] = 0

            # Calculate implied NO price
            enriched['no_price_cents'] = 100 - enriched['yes_price_cents']

            # Get bid/ask prices
            yes_bid_str = market.get('yes_bid_dollars', '0')
            yes_ask_str = market.get('yes_ask_dollars', '0')
            try:
                enriched['yes_bid_cents'] = int(float(yes_bid_str) * 100)
            except (ValueError, TypeError):
                enriched['yes_bid_cents'] = 0

            try:
                enriched['yes_ask_cents'] = int(float(yes_ask_str) * 100)
            except (ValueError, TypeError):
                enriched['yes_ask_cents'] = 0

            # Calculate spread
            if enriched['yes_bid_cents'] > 0 and enriched['yes_ask_cents'] > 0:
                enriched['spread_cents'] = enriched['yes_ask_cents'] - enriched['yes_bid_cents']
            else:
                enriched['spread_cents'] = None

            # Get volume metrics
            enriched['volume'] = market.get('volume', 0)
            enriched['volume_24h'] = market.get('volume_24h', 0)
            enriched['open_interest'] = market.get('open_interest', 0)

            # Parse close time
            close_time_str = market.get('close_time')
            if close_time_str:
                try:
                    enriched['close_time_dt'] = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    enriched['close_time_dt'] = None
            else:
                enriched['close_time_dt'] = None

            # Get outcome/strike name
            # Try different fields that might contain the outcome description
            outcome = market.get('yes_sub_title') or market.get('subtitle') or market.get('title', '')
            if not outcome:
                # Try to extract from ticker
                ticker = market.get('ticker', '')
                outcome = ticker
            enriched['outcome'] = outcome

            enriched_markets.append(enriched)

        # Sort markets
        sort_functions = {
            'price': lambda m: (-m['yes_price_cents'], m.get('outcome', '')),
            'volume': lambda m: (-m['volume'], -m['yes_price_cents']),
            'strike': lambda m: m.get('outcome', ''),
            'spread': lambda m: (m['spread_cents'] if m['spread_cents'] is not None else 999, -m['yes_price_cents'])
        }
        sort_func = sort_functions.get(sort_by, sort_functions['price'])
        enriched_markets.sort(key=sort_func)

        # Calculate sum of probabilities (for mutually exclusive events)
        sum_yes_prices = sum(m['yes_price_cents'] for m in enriched_markets)
        is_mutually_exclusive = event.get('mutually_exclusive', False)

        # Arbitrage analysis for mutually exclusive events
        arb_analysis = None
        if is_mutually_exclusive and len(enriched_markets) > 1:
            deviation_cents = sum_yes_prices - 100
            arb_analysis = {
                'sum_yes_prices_cents': sum_yes_prices,
                'sum_yes_prices_dollars': sum_yes_prices / 100,
                'deviation_cents': deviation_cents,
                'deviation_dollars': deviation_cents / 100,
                'opportunity': 'none'
            }
            if deviation_cents < -1:  # Sum < 99 cents (potential buy arb)
                arb_analysis['opportunity'] = 'buy_all'
                arb_analysis['description'] = f"Sum of YES prices is ${sum_yes_prices/100:.2f} (< $1.00). Buying all outcomes costs ${sum_yes_prices/100:.2f}, guaranteed payout is $1.00. Potential profit: ${abs(deviation_cents)/100:.2f} before fees."
            elif deviation_cents > 1:  # Sum > 101 cents (potential sell arb)
                arb_analysis['opportunity'] = 'sell_all'
                arb_analysis['description'] = f"Sum of YES prices is ${sum_yes_prices/100:.2f} (> $1.00). Selling all outcomes yields ${sum_yes_prices/100:.2f}, max loss is $1.00. Potential profit: ${deviation_cents/100:.2f} before fees."
            else:
                arb_analysis['description'] = f"Sum of YES prices is ${sum_yes_prices/100:.2f} (approximately $1.00). Market is efficiently priced - no obvious arbitrage."

        # Calculate event-level metrics
        total_volume = sum(m['volume'] for m in enriched_markets)
        total_volume_24h = sum(m['volume_24h'] for m in enriched_markets)
        total_open_interest = sum(m['open_interest'] for m in enriched_markets)

        # Get earliest close time
        close_times = [m['close_time_dt'] for m in enriched_markets if m['close_time_dt']]
        earliest_close = min(close_times) if close_times else None

        print("Analysis complete", file=sys.stderr)

        return {
            'event': {
                'ticker': event.get('event_ticker', ''),
                'title': event.get('title', ''),
                'subtitle': event.get('sub_title', ''),
                'category': event.get('category', ''),
                'series_ticker': event.get('series_ticker', ''),
                'status': event.get('status', ''),
                'mutually_exclusive': is_mutually_exclusive,
                'strike_type': event.get('strike_type', ''),
            },
            'markets': enriched_markets,
            'summary': {
                'market_count': len(enriched_markets),
                'total_volume': total_volume,
                'total_volume_24h': total_volume_24h,
                'total_open_interest': total_open_interest,
                'earliest_close': earliest_close.isoformat() if earliest_close else None,
                'sum_yes_prices_cents': sum_yes_prices,
                'sort_by': sort_by
            },
            'arbitrage_analysis': arb_analysis,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }


def format_number(num: int) -> str:
    """Format large numbers with K, M, B suffixes."""
    if num >= 1_000_000_000:
        return f"{num/1_000_000_000:.1f}B"
    elif num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num/1_000:.1f}K"
    return str(num)


def format_price_cents(cents: int) -> str:
    """Format cents as dollar string."""
    if cents == 0:
        return "-"
    return f"${cents/100:.2f}"


def format_close_time(close_dt: Optional[datetime]) -> str:
    """Format close datetime as readable string."""
    if not close_dt:
        return "Unknown"

    now = datetime.utcnow()
    delta = close_dt.replace(tzinfo=None) - now

    if delta.days < 0:
        return "Closed"
    elif delta.days == 0:
        hours = delta.seconds // 3600
        if hours == 0:
            minutes = delta.seconds // 60
            return f"{minutes}m"
        return f"{hours}h"
    elif delta.days < 7:
        return f"{delta.days}d"
    elif delta.days < 30:
        weeks = delta.days // 7
        return f"{weeks}w"
    else:
        months = delta.days // 30
        return f"{months}mo"


def display_with_rich(analysis: Dict[str, Any]):
    """Display event analysis using rich library for beautiful terminal output."""
    console = Console()
    event = analysis['event']
    summary = analysis['summary']
    markets = analysis['markets']
    arb = analysis['arbitrage_analysis']

    # Header panel with event info
    header = Text()
    header.append("EVENT DRILL-DOWN\n", style="bold cyan")
    header.append(f"\n{event['title']}\n", style="bold white")
    if event.get('subtitle'):
        header.append(f"{event['subtitle']}\n", style="dim")

    header.append(f"\nTicker: ", style="bold")
    header.append(f"{event['ticker']}\n", style="yellow")
    header.append(f"Category: ", style="bold")
    header.append(f"{event['category']}\n", style="cyan")
    header.append(f"Series: ", style="bold")
    header.append(f"{event['series_ticker']}\n", style="dim")
    header.append(f"Status: ", style="bold")
    status_style = "green" if event['status'] == 'open' else "red"
    header.append(f"{event['status']}\n", style=status_style)

    header.append(f"\nMutually Exclusive: ", style="bold")
    me_style = "green bold" if event['mutually_exclusive'] else "dim"
    header.append(f"{'YES' if event['mutually_exclusive'] else 'NO'}", style=me_style)
    if event['mutually_exclusive']:
        header.append(" (only one outcome can win)", style="dim")

    console.print(Panel(header, border_style="cyan"))

    # Summary stats
    console.print("\n[bold cyan]EVENT SUMMARY[/bold cyan]")
    stats_table = Table(box=box.SIMPLE, show_header=False)
    stats_table.add_column("Metric", style="bold")
    stats_table.add_column("Value", style="yellow")

    stats_table.add_row("Markets", str(summary['market_count']))
    stats_table.add_row("Total Volume", format_number(summary['total_volume']))
    stats_table.add_row("24h Volume", format_number(summary['total_volume_24h']))
    stats_table.add_row("Open Interest", format_number(summary['total_open_interest']))
    stats_table.add_row("Earliest Close", format_close_time(
        datetime.fromisoformat(summary['earliest_close'].replace('Z', '+00:00')) if summary['earliest_close'] else None
    ))
    stats_table.add_row("Sum of YES Prices", f"${summary['sum_yes_prices_cents']/100:.2f}")

    console.print(stats_table)

    # Arbitrage analysis (for mutually exclusive events)
    if arb:
        console.print("\n[bold cyan]ARBITRAGE ANALYSIS[/bold cyan]")
        if arb['opportunity'] == 'buy_all':
            console.print(Panel(arb['description'], border_style="green", title="[green]Potential Buy Arbitrage[/green]"))
        elif arb['opportunity'] == 'sell_all':
            console.print(Panel(arb['description'], border_style="green", title="[green]Potential Sell Arbitrage[/green]"))
        else:
            console.print(Panel(arb['description'], border_style="dim", title="Market Efficiency"))

    # Markets table - compact design for typical terminal widths (~80-100 chars)
    console.print(f"\n[bold cyan]ALL MARKETS (sorted by {summary['sort_by']})[/bold cyan]\n")

    markets_table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
    markets_table.add_column("#", justify="right", style="dim", width=2)
    markets_table.add_column("Outcome", style="white", width=22, no_wrap=True, overflow="ellipsis")
    markets_table.add_column("YES", justify="right", style="green", width=4)
    markets_table.add_column("Bid/Ask", justify="center", style="cyan", width=7)
    markets_table.add_column("Sprd", justify="right", style="yellow", width=4)
    markets_table.add_column("Volume", justify="right", style="blue", width=6)
    markets_table.add_column("24h", justify="right", style="blue", width=5)
    markets_table.add_column("OI", justify="right", style="magenta", width=5)

    for i, market in enumerate(markets, 1):
        outcome = market['outcome']
        if len(outcome) > 22:
            outcome = outcome[:19] + "..."

        # Combine bid/ask into compact format
        bid = market['yes_bid_cents']
        ask = market['yes_ask_cents']
        if bid > 0 and ask > 0:
            bid_ask_str = f"{bid}/{ask}"
        elif bid > 0:
            bid_ask_str = f"{bid}/-"
        elif ask > 0:
            bid_ask_str = f"-/{ask}"
        else:
            bid_ask_str = "-"

        spread_str = str(market['spread_cents']) if market['spread_cents'] is not None else "-"

        markets_table.add_row(
            str(i),
            outcome,
            f"{market['yes_price_cents']}¢",
            bid_ask_str,
            spread_str,
            format_number(market['volume']),
            format_number(market['volume_24h']),
            format_number(market['open_interest'])
        )

    console.print(markets_table)

    # Footer with tips
    console.print("\n[dim]Column guide: YES=last price, Bid/Ask=best bid/ask, Sprd=spread, OI=open interest[/dim]")
    console.print("[dim]Tip: For mutually exclusive events, sum of YES prices should ≈ $1.00[/dim]")
    console.print()


def display_plain(analysis: Dict[str, Any]):
    """Plain text output for when rich is not available."""
    event = analysis['event']
    summary = analysis['summary']
    markets = analysis['markets']
    arb = analysis['arbitrage_analysis']

    print("=" * 80)
    print("EVENT DRILL-DOWN")
    print("=" * 80)
    print(f"\nTitle: {event['title']}")
    if event.get('subtitle'):
        print(f"Subtitle: {event['subtitle']}")
    print(f"\nTicker: {event['ticker']}")
    print(f"Category: {event['category']}")
    print(f"Series: {event['series_ticker']}")
    print(f"Status: {event['status']}")
    print(f"Mutually Exclusive: {'YES' if event['mutually_exclusive'] else 'NO'}")

    print("\n" + "-" * 80)
    print("EVENT SUMMARY")
    print("-" * 80)
    print(f"Markets: {summary['market_count']}")
    print(f"Total Volume: {summary['total_volume']:,}")
    print(f"24h Volume: {summary['total_volume_24h']:,}")
    print(f"Open Interest: {summary['total_open_interest']:,}")
    print(f"Sum of YES Prices: ${summary['sum_yes_prices_cents']/100:.2f}")

    if arb:
        print("\n" + "-" * 80)
        print("ARBITRAGE ANALYSIS")
        print("-" * 80)
        print(arb['description'])

    print("\n" + "-" * 80)
    print(f"ALL MARKETS (sorted by {summary['sort_by']})")
    print("-" * 80)

    for i, market in enumerate(markets, 1):
        print(f"\n{i}. {market['outcome']}")
        print(f"   Ticker: {market.get('ticker', 'N/A')}")
        print(f"   YES: {market['yes_price_cents']}¢ | NO: {market['no_price_cents']}¢")
        print(f"   Bid: {market['yes_bid_cents']}¢ | Ask: {market['yes_ask_cents']}¢ | Spread: {market['spread_cents']}¢")
        print(f"   Volume: {market['volume']:,} | 24h: {market['volume_24h']:,} | Open Int: {market['open_interest']:,}")


def format_csv(analysis: Dict[str, Any]) -> str:
    """Format analysis as CSV."""
    event = analysis['event']
    markets = analysis['markets']

    lines = [
        f"# Event: {event['title']}",
        f"# Ticker: {event['ticker']}",
        f"# Category: {event['category']}",
        f"# Mutually Exclusive: {event['mutually_exclusive']}",
        "",
        "ticker,outcome,yes_price_cents,no_price_cents,bid_cents,ask_cents,spread_cents,volume,volume_24h,open_interest"
    ]

    for market in markets:
        outcome = market['outcome'].replace('"', '""')
        spread = market['spread_cents'] if market['spread_cents'] is not None else ''
        lines.append(
            f"{market.get('ticker', '')},"
            f"\"{outcome}\","
            f"{market['yes_price_cents']},"
            f"{market['no_price_cents']},"
            f"{market['yes_bid_cents']},"
            f"{market['yes_ask_cents']},"
            f"{spread},"
            f"{market['volume']},"
            f"{market['volume_24h']},"
            f"{market['open_interest']}"
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Drill down into a specific Kalshi event to see all markets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python event_drilldown.py FED-26JAN29           # Analyze Fed rate event
  python event_drilldown.py INXD-26JAN24 --sort volume  # Sort by volume
  python event_drilldown.py CPI-26FEB14 -o cpi.json --output-format json
        '''
    )
    parser.add_argument(
        'event_ticker',
        metavar='EVENT_TICKER',
        help='The event ticker to analyze (e.g., FED-26JAN29, INXD-26JAN24)'
    )
    parser.add_argument(
        '--sort',
        choices=['price', 'volume', 'strike', 'spread'],
        default='price',
        help='Sort order for markets: price (highest first), volume, strike (alphabetical), spread (tightest first) (default: price)'
    )
    parser.add_argument(
        '--output-format',
        choices=['json', 'csv', 'console'],
        default='console',
        help='Output format (default: console)'
    )
    parser.add_argument(
        '--output-file', '-o',
        help='Output file path (default: stdout)'
    )

    args = parser.parse_args()

    try:
        client = KalshiEventDrilldown()
        event = client.get_event(args.event_ticker)
        analysis = client.analyze_event(event, sort_by=args.sort)

        # Generate output
        if args.output_format == 'json':
            # Custom JSON encoder for datetime
            def json_serializer(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

            output = json.dumps(analysis, indent=2, default=json_serializer)
        elif args.output_format == 'csv':
            output = format_csv(analysis)
        else:  # console
            if args.output_file:
                # If saving to file, use plain text
                import io
                buf = io.StringIO()
                old_stdout = sys.stdout
                sys.stdout = buf
                display_plain(analysis)
                sys.stdout = old_stdout
                output = buf.getvalue()
            else:
                # Display to terminal with rich if available
                if RICH_AVAILABLE:
                    display_with_rich(analysis)
                else:
                    display_plain(analysis)
                return 0

        # Write output if file specified
        if args.output_file:
            with open(args.output_file, 'w') as f:
                f.write(output)
            print(f"Output saved to {args.output_file}", file=sys.stderr)
        else:
            print(output)

        return 0

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 1
    except requests.exceptions.HTTPError:
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
