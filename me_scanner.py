#!/usr/bin/env python3
"""
Kalshi Mutually Exclusive Event Scanner

PURPOSE:
    Scan all mutually exclusive events to find:
    1. Certainty Gap opportunities (markets priced 80-97¢)
    2. Sum-of-probabilities arbitrage (when sum of YES prices != $1.00)

USAGE:
    # Find ME events with high-confidence markets (80-97¢)
    python me_scanner.py --min-price 80 --max-price 97

    # Find all ME events, check for arbitrage
    python me_scanner.py

    # Focus on specific category
    python me_scanner.py --category Economics --min-price 80

    # Sort by arbitrage opportunity (biggest deviation from $1.00)
    python me_scanner.py --sort arb

    # Export to JSON
    python me_scanner.py --output-format json -o me_events.json
"""

import argparse
import json
import sys
from datetime import datetime, timezone
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


BASE_URL = "https://api.elections.kalshi.com/trade-api/v2/"


class MEScanner:
    """Scanner for mutually exclusive events."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'Kalshi-ME-Scanner/1.0'
        })

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request to API endpoint."""
        url = urljoin(self.base_url, endpoint)
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {endpoint}: {e}", file=sys.stderr)
            raise

    def get_all_events(self, status: str = 'open') -> List[Dict[str, Any]]:
        """Fetch all events with pagination."""
        print(f"Fetching all {status} events...", file=sys.stderr)

        all_events = []
        cursor = None
        page = 1

        while True:
            params = {
                'limit': 200,
                'status': status,
                'with_nested_markets': 'true'
            }
            if cursor:
                params['cursor'] = cursor

            data = self._get('events', params=params)
            events = data.get('events', [])

            if not events:
                break

            all_events.extend(events)
            print(f"  Page {page}: +{len(events)} events (total: {len(all_events)})", file=sys.stderr)

            cursor = data.get('cursor', '')
            if not cursor:
                break
            page += 1

        print(f"Fetched {len(all_events)} total events", file=sys.stderr)
        return all_events

    def scan_me_events(
        self,
        events: List[Dict[str, Any]],
        min_price: int = 0,
        max_price: int = 100,
        min_volume: int = 0,
        min_arb: int = 3,
        category_filter: Optional[str] = None,
        sort_by: str = 'price'
    ) -> Dict[str, Any]:
        """
        Scan for mutually exclusive events matching criteria.

        Args:
            events: List of all events
            min_price: Minimum price filter (at least one market must be >= this)
            max_price: Maximum price filter (at least one market must be <= this)
            min_volume: Minimum total volume for event
            min_arb: Minimum arb deviation to include (filters out noise near $1.00)
            category_filter: Filter to specific category
            sort_by: Sort method (price, volume, arb, closing)

        Returns:
            Dictionary with scan results
        """
        print(f"Scanning for ME events (price {min_price}-{max_price}¢, min arb ±{min_arb}¢)...", file=sys.stderr)

        me_events = []

        for event in events:
            # Skip non-ME events
            if not event.get('mutually_exclusive', False):
                continue

            markets = event.get('markets', [])
            if not markets:
                continue

            # Calculate metrics for each market
            market_data = []
            for m in markets:
                price_str = m.get('last_price_dollars') or m.get('yes_bid_dollars', '0')
                try:
                    price_cents = int(float(price_str) * 100)
                except (ValueError, TypeError):
                    price_cents = 0

                bid_str = m.get('yes_bid_dollars', '0')
                ask_str = m.get('yes_ask_dollars', '0')
                try:
                    bid_cents = int(float(bid_str) * 100)
                except (ValueError, TypeError):
                    bid_cents = 0
                try:
                    ask_cents = int(float(ask_str) * 100)
                except (ValueError, TypeError):
                    ask_cents = 0

                market_data.append({
                    'ticker': m.get('ticker', ''),
                    'outcome': m.get('yes_sub_title') or m.get('subtitle') or m.get('title', ''),
                    'price_cents': price_cents,
                    'bid_cents': bid_cents,
                    'ask_cents': ask_cents,
                    'volume': m.get('volume', 0),
                    'volume_24h': m.get('volume_24h', 0),
                    'open_interest': m.get('open_interest', 0),
                    'close_time': m.get('close_time')
                })

            # Calculate event-level metrics
            prices = [md['price_cents'] for md in market_data]
            total_volume = sum(md['volume'] for md in market_data)
            total_volume_24h = sum(md['volume_24h'] for md in market_data)
            total_oi = sum(md['open_interest'] for md in market_data)
            sum_yes = sum(prices)

            max_market_price = max(prices) if prices else 0
            min_market_price = min(prices) if prices else 0

            # Apply filters
            if total_volume < min_volume:
                continue

            # Price filter: event has at least one market in the specified range
            has_market_in_range = any(min_price <= p <= max_price for p in prices)
            if not has_market_in_range:
                continue

            # Category filter
            event_category = event.get('category', 'Unknown')
            if category_filter and event_category != category_filter:
                continue

            # Find the highest-priced market in range (the "certainty gap" candidate)
            markets_in_range = [md for md in market_data if min_price <= md['price_cents'] <= max_price]
            markets_in_range.sort(key=lambda x: x['price_cents'], reverse=True)
            top_market = markets_in_range[0] if markets_in_range else None

            # Parse close time
            close_times = []
            for md in market_data:
                if md['close_time']:
                    try:
                        close_dt = datetime.fromisoformat(md['close_time'].replace('Z', '+00:00'))
                        close_times.append(close_dt)
                    except (ValueError, TypeError):
                        continue
            earliest_close = min(close_times) if close_times else None

            # Calculate arbitrage metrics
            arb_deviation = sum_yes - 100  # cents from $1.00

            # Filter out noise near $1.00 (e.g., 98-102 range is likely just spread)
            if abs(arb_deviation) < min_arb:
                continue

            me_events.append({
                'event_ticker': event.get('event_ticker', ''),
                'title': event.get('title', ''),
                'category': event_category,
                'market_count': len(market_data),
                'sum_yes_cents': sum_yes,
                'arb_deviation': arb_deviation,
                'max_price': max_market_price,
                'min_price': min_market_price,
                'total_volume': total_volume,
                'total_volume_24h': total_volume_24h,
                'total_oi': total_oi,
                'earliest_close': earliest_close,
                'top_market': top_market,
                'markets_in_range': len(markets_in_range),
                'all_markets': market_data
            })

        # Sort results
        sort_funcs = {
            'price': lambda x: -(x['top_market']['price_cents'] if x['top_market'] else 0),
            'volume': lambda x: -x['total_volume'],
            'arb': lambda x: -abs(x['arb_deviation']),
            'closing': lambda x: x['earliest_close'] or datetime.max.replace(tzinfo=timezone.utc)
        }
        sort_func = sort_funcs.get(sort_by, sort_funcs['price'])
        me_events.sort(key=sort_func)

        print(f"Found {len(me_events)} ME events matching criteria", file=sys.stderr)

        return {
            'metadata': {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'total_events_scanned': len(events),
                'me_events_found': len(me_events),
                'filters': {
                    'min_price': min_price,
                    'max_price': max_price,
                    'min_volume': min_volume,
                    'min_arb': min_arb,
                    'category': category_filter
                },
                'sort_by': sort_by
            },
            'events': me_events
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


def format_close_time(close_dt: Optional[datetime]) -> str:
    """Format close datetime as readable string."""
    if not close_dt:
        return "Unknown"

    now = datetime.now(timezone.utc)
    delta = close_dt.replace(tzinfo=None) - now.replace(tzinfo=None)

    if delta.days < 0:
        return "Closed"
    elif delta.days == 0:
        hours = delta.seconds // 3600
        return f"{hours}h"
    elif delta.days < 7:
        return f"{delta.days}d"
    elif delta.days < 30:
        weeks = delta.days // 7
        return f"{weeks}w"
    else:
        months = delta.days // 30
        return f"{months}mo"


def display_with_rich(results: Dict[str, Any]):
    """Display results using rich library."""
    console = Console()
    meta = results['metadata']
    events = results['events']

    # Header
    header = Text()
    header.append("MUTUALLY EXCLUSIVE EVENT SCANNER\n", style="bold cyan")
    header.append(f"\nScanned: {meta['total_events_scanned']} events\n", style="dim")
    if 'limited_to' in meta:
        header.append(f"Showing: {meta['limited_to']} of {meta['total_matching']} matching ME events\n", style="bold green")
    else:
        header.append(f"Found: {meta['me_events_found']} ME events matching criteria\n", style="bold green")

    filters = meta['filters']
    filter_str = f"Price range: {filters['min_price']}-{filters['max_price']}¢"
    if filters['min_arb'] > 0:
        filter_str += f", arb ±{filters['min_arb']}¢+"
    if filters['min_volume'] > 0:
        filter_str += f", min vol: {format_number(filters['min_volume'])}"
    if filters['category']:
        filter_str += f", category: {filters['category']}"
    header.append(f"Filters: {filter_str}\n", style="dim")
    header.append(f"Sort: {meta['sort_by']}", style="dim")

    console.print(Panel(header, border_style="cyan"))

    if not events:
        console.print("\n[yellow]No events found matching criteria.[/yellow]")
        return

    # Main table
    console.print(f"\n[bold cyan]ME EVENTS (sorted by {meta['sort_by']})[/bold cyan]\n")

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta", expand=True)
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Event", style="white", width=30, no_wrap=True, overflow="ellipsis")
    table.add_column("Ticker", style="yellow", width=16)
    table.add_column("Cat", style="cyan", width=8)
    table.add_column("Top Mkt", style="green", width=18, no_wrap=True, overflow="ellipsis")
    table.add_column("Price", justify="right", style="bold green", width=5)
    table.add_column("Sum", justify="right", style="magenta", width=5)
    table.add_column("Arb", justify="right", width=4)
    table.add_column("Vol", justify="right", style="blue", width=6)
    table.add_column("Close", justify="right", style="dim", width=5)

    for i, event in enumerate(events, 1):
        title = event['title']
        if len(title) > 30:
            title = title[:27] + "..."

        top_mkt = event['top_market']
        top_outcome = top_mkt['outcome'] if top_mkt else "-"
        if len(top_outcome) > 18:
            top_outcome = top_outcome[:15] + "..."
        top_price = f"{top_mkt['price_cents']}¢" if top_mkt else "-"

        sum_str = f"${event['sum_yes_cents']/100:.2f}"

        # Color arb deviation
        arb = event['arb_deviation']
        if arb < -2:
            arb_str = f"[green]{arb:+d}[/green]"
        elif arb > 2:
            arb_str = f"[red]{arb:+d}[/red]"
        else:
            arb_str = f"[dim]{arb:+d}[/dim]"

        table.add_row(
            str(i),
            title,
            event['event_ticker'],
            event['category'][:8],
            top_outcome,
            top_price,
            sum_str,
            arb_str,
            format_number(event['total_volume']),
            format_close_time(event['earliest_close'])
        )

    console.print(table)

    # Legend
    console.print("\n[dim]Column guide: Top Mkt=highest-priced market in filter range, Sum=sum of YES prices, Arb=deviation from $1.00[/dim]")
    console.print("[dim]Arb interpretation: negative=potential buy arb, positive=potential sell arb[/dim]")
    console.print()


def display_plain(results: Dict[str, Any]):
    """Plain text output."""
    meta = results['metadata']
    events = results['events']

    print("=" * 80)
    print("MUTUALLY EXCLUSIVE EVENT SCANNER")
    print("=" * 80)
    print(f"Scanned: {meta['total_events_scanned']} events")
    if 'limited_to' in meta:
        print(f"Showing: {meta['limited_to']} of {meta['total_matching']} matching ME events")
    else:
        print(f"Found: {meta['me_events_found']} ME events matching criteria")
    print(f"Filters: {meta['filters']}")
    print(f"Sort: {meta['sort_by']}")
    print()

    for i, event in enumerate(events, 1):
        print(f"\n{i}. {event['title']}")
        print(f"   Ticker: {event['event_ticker']} | Category: {event['category']}")
        if event['top_market']:
            print(f"   Top Market: {event['top_market']['outcome']} @ {event['top_market']['price_cents']}¢")
        print(f"   Sum of YES: ${event['sum_yes_cents']/100:.2f} | Arb deviation: {event['arb_deviation']:+d}¢")
        print(f"   Volume: {event['total_volume']:,} | Markets: {event['market_count']}")


def format_csv(results: Dict[str, Any]) -> str:
    """Format as CSV."""
    lines = [
        "event_ticker,title,category,market_count,sum_yes_cents,arb_deviation,top_market_outcome,top_market_price,total_volume,earliest_close"
    ]

    for event in results['events']:
        title = event['title'].replace('"', '""')
        top_mkt = event['top_market']
        top_outcome = (top_mkt['outcome'].replace('"', '""') if top_mkt else '')
        top_price = (top_mkt['price_cents'] if top_mkt else '')
        close = event['earliest_close'].isoformat() if event['earliest_close'] else ''

        lines.append(
            f"{event['event_ticker']},"
            f"\"{title}\","
            f"{event['category']},"
            f"{event['market_count']},"
            f"{event['sum_yes_cents']},"
            f"{event['arb_deviation']},"
            f"\"{top_outcome}\","
            f"{top_price},"
            f"{event['total_volume']},"
            f"{close}"
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Scan mutually exclusive events for certainty gaps and arbitrage',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python me_scanner.py --min-price 80 --max-price 97   # Certainty gap candidates
  python me_scanner.py --sort arb                       # Biggest arb opportunities
  python me_scanner.py --category Economics             # Economics only
  python me_scanner.py --limit 50                       # Show top 50 results
  python me_scanner.py --limit 0                        # Show all results
        '''
    )
    parser.add_argument(
        '--min-price',
        type=int,
        default=0,
        help='Minimum price in cents (event must have market >= this) (default: 0)'
    )
    parser.add_argument(
        '--max-price',
        type=int,
        default=100,
        help='Maximum price in cents (event must have market <= this) (default: 100)'
    )
    parser.add_argument(
        '--min-volume',
        type=int,
        default=0,
        help='Minimum total volume for event (default: 0)'
    )
    parser.add_argument(
        '--min-arb',
        type=int,
        default=3,
        help='Minimum arb deviation in cents to include (default: 3, filters out 98-102 noise)'
    )
    parser.add_argument(
        '--category',
        type=str,
        help='Filter to specific category'
    )
    parser.add_argument(
        '--sort',
        choices=['price', 'volume', 'arb', 'closing'],
        default='price',
        help='Sort order: price (highest in-range), volume, arb (biggest deviation), closing (soonest) (default: price)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Maximum results for console output (default: 50, use 0 for unlimited). Does not affect CSV/JSON exports.'
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
        scanner = MEScanner()
        events = scanner.get_all_events(status='open')
        results = scanner.scan_me_events(
            events,
            min_price=args.min_price,
            max_price=args.max_price,
            min_volume=args.min_volume,
            min_arb=args.min_arb,
            category_filter=args.category,
            sort_by=args.sort
        )

        if args.output_format == 'json':
            output = json.dumps(results, indent=2, default=str)
        elif args.output_format == 'csv':
            output = format_csv(results)
        else:
            # Apply limit only for console output
            if args.limit > 0 and len(results['events']) > args.limit:
                total_found = len(results['events'])
                results['events'] = results['events'][:args.limit]
                results['metadata']['limited_to'] = args.limit
                results['metadata']['total_matching'] = total_found
                print(f"Showing top {args.limit} of {total_found} results (use --limit 0 for all)", file=sys.stderr)

            if args.output_file:
                import io
                buf = io.StringIO()
                old_stdout = sys.stdout
                sys.stdout = buf
                display_plain(results)
                sys.stdout = old_stdout
                output = buf.getvalue()
            else:
                if RICH_AVAILABLE:
                    display_with_rich(results)
                else:
                    display_plain(results)
                return 0

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
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
