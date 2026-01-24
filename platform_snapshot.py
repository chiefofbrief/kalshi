#!/usr/bin/env python3
"""
Kalshi Platform Snapshot Script - Level 1 Platform Crawler

PURPOSE:
    Discover what exists on the Kalshi prediction market platform and what's
    actually being traded. Identifies high-liquidity markets and filters out
    low-volume "ghost towns."

WHAT IT DOES:
    - Fetches all series and events from the Kalshi API (public, no auth needed)
    - Handles pagination automatically (4000+ events across multiple pages)
    - Groups data by category and sorts by trading volume
    - Displays beautiful terminal tables with statistics and rankings
    - Optionally exports to JSON/CSV for deeper analysis

USAGE:
    # Default: Show markets with 50k+ volume in formatted terminal
    python platform_snapshot.py

    # Lower threshold to see more markets
    python platform_snapshot.py --min-volume 10000

    # See everything (warning: 4000+ events!)
    python platform_snapshot.py --min-volume 0

    # Export full data for analysis
    python platform_snapshot.py --output-format json -o snapshot.json
    python platform_snapshot.py --output-format csv -o markets.csv

    # Fetch closed or settled events
    python platform_snapshot.py --status closed

OPTIONS:
    --min-volume      Minimum volume threshold (default: 50000)
    --status          Event status: open, closed, settled (default: open)
    --output-format   json, csv, or console (default: console)
    --output-file     Save to file instead of stdout
    --top-n           Number of top events/series to show (default: 25)

API ENDPOINTS USED:
    GET /series           - All series with volume data
    GET /events           - All events with pagination (200 per page)

    Both are public endpoints (no authentication required)

INSTALLATION:
    pip install requests rich

EXAMPLE OUTPUT:
    Platform Summary: 8,104 series, 4,051 events, 761M contracts
    After filter (50k+): 583 events across 15 categories

    Top categories: Sports (397M), Politics (224M), Economics (39M)
    Top event: Pro Football Champion (133M contracts, 32 markets)

NEXT STEPS:
    After running this snapshot, you can:
    1. Drill down into specific events with GET /events/{ticker}
    2. Look for arbitrage in mutually exclusive events
    3. Analyze order book spreads for trading efficiency
    4. Monitor real-time data (requires authentication)
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


class KalshiSnapshot:
    """Client for fetching Kalshi platform snapshot data."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'Kalshi-Platform-Snapshot/1.0'
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

    def get_all_series(self, include_volume: bool = True) -> List[Dict[str, Any]]:
        """Fetch all series from the platform with volume data."""
        print("Fetching all series...", file=sys.stderr)
        params = {'include_volume': str(include_volume).lower()}
        data = self._get('series', params=params)
        series_list = data.get('series', [])
        print(f"✓ Found {len(series_list)} series", file=sys.stderr)
        return series_list

    def get_all_events(
        self,
        status: str = 'open',
        with_nested_markets: bool = True,
    ) -> List[Dict[str, Any]]:
        """Fetch all events from the platform with automatic pagination."""
        print(f"Fetching all {status} events...", file=sys.stderr)

        all_events = []
        cursor = None
        page = 1

        while True:
            params = {
                'limit': 200,
                'status': status,
                'with_nested_markets': str(with_nested_markets).lower()
            }
            if cursor:
                params['cursor'] = cursor

            data = self._get('events', params=params)
            events = data.get('events', [])

            if not events:
                break

            all_events.extend(events)
            print(f"  Page {page}: +{len(events)} events (total: {len(all_events)})",
                  file=sys.stderr)

            cursor = data.get('cursor', '')
            if not cursor:
                break
            page += 1

        print(f"✓ Total events fetched: {len(all_events)}", file=sys.stderr)
        return all_events

    def analyze_snapshot(
        self,
        series: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
        min_volume: int = 0
    ) -> Dict[str, Any]:
        """Analyze and organize snapshot data by category and volume."""
        print(f"Analyzing snapshot (min_volume={min_volume:,})...", file=sys.stderr)

        # Calculate volume for each event from nested markets
        for event in events:
            event_volume = sum(m.get('volume', 0) for m in event.get('markets', []))
            event['calculated_volume'] = event_volume

        # Group and sort series by category
        series_by_category = {}
        for s in series:
            category = s.get('category', 'Unknown')
            series_by_category.setdefault(category, []).append(s)

        for category in series_by_category:
            series_by_category[category].sort(key=lambda x: x.get('volume', 0), reverse=True)

        # Group and filter events by category
        events_by_category = {}
        total_volume = sum(e['calculated_volume'] for e in events)

        for event in events:
            if event['calculated_volume'] >= min_volume:
                category = event.get('category', 'Unknown')
                events_by_category.setdefault(category, []).append(event)

        # Sort events within each category by volume
        for category in events_by_category:
            events_by_category[category].sort(
                key=lambda x: x['calculated_volume'],
                reverse=True
            )

        # Generate category statistics
        category_stats = {}
        for category, events_list in events_by_category.items():
            total_cat_volume = sum(e['calculated_volume'] for e in events_list)
            category_stats[category] = {
                'event_count': len(events_list),
                'total_volume': total_cat_volume,
                'avg_volume': total_cat_volume / len(events_list) if events_list else 0
            }

        print(f"✓ Analysis complete", file=sys.stderr)

        return {
            'metadata': {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'total_series': len(series),
                'total_events': len(events),
                'events_after_filter': sum(len(v) for v in events_by_category.values()),
                'total_volume': total_volume,
                'min_volume_filter': min_volume,
                'categories': sorted(events_by_category.keys())
            },
            'series_by_category': series_by_category,
            'events_by_category': events_by_category,
            'category_statistics': category_stats
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


def display_with_rich(snapshot: Dict[str, Any], top_n: int = 25):
    """Display snapshot using rich library for beautiful terminal output."""
    console = Console()
    meta = snapshot['metadata']

    # Header panel
    header = Text()
    header.append("KALSHI PLATFORM SNAPSHOT\n", style="bold cyan")
    header.append(f"Timestamp: {meta['timestamp']}\n", style="dim")
    header.append(f"\nPlatform: ", style="bold")
    header.append(f"{meta['total_series']:,} series, {meta['total_events']:,} events, ")
    header.append(f"{format_number(meta['total_volume'])} contracts\n")
    header.append(f"After filter (≥{meta['min_volume_filter']:,}): ", style="bold")
    header.append(f"{meta['events_after_filter']:,} events across {len(meta['categories'])} categories")

    console.print(Panel(header, border_style="cyan"))

    # Category Statistics Table
    console.print("\n[bold cyan]CATEGORY STATISTICS[/bold cyan]\n")
    cat_table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
    cat_table.add_column("Category", style="cyan", no_wrap=True)
    cat_table.add_column("Events", justify="right", style="green")
    cat_table.add_column("Total Volume", justify="right", style="yellow")
    cat_table.add_column("Avg/Event", justify="right", style="blue")

    stats = snapshot['category_statistics']
    sorted_cats = sorted(stats.items(), key=lambda x: x[1]['total_volume'], reverse=True)

    for category, cat_stats in sorted_cats:
        cat_table.add_row(
            category,
            f"{cat_stats['event_count']:,}",
            format_number(cat_stats['total_volume']),
            format_number(int(cat_stats['avg_volume']))
        )

    console.print(cat_table)

    # Top Events Table
    console.print(f"\n[bold cyan]TOP {top_n} EVENTS BY VOLUME[/bold cyan]\n")
    events_table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
    events_table.add_column("#", justify="right", style="dim", width=3)
    events_table.add_column("Event", style="white", max_width=50)
    events_table.add_column("Category", style="cyan", no_wrap=True)
    events_table.add_column("Volume", justify="right", style="yellow")
    events_table.add_column("Markets", justify="right", style="green")

    all_events = []
    for events_list in snapshot['events_by_category'].values():
        all_events.extend(events_list)
    all_events.sort(key=lambda x: x['calculated_volume'], reverse=True)

    for i, event in enumerate(all_events[:top_n], 1):
        title = event.get('title', 'Unknown')
        if len(title) > 50:
            title = title[:47] + "..."

        events_table.add_row(
            str(i),
            title,
            event.get('category', 'Unknown'),
            format_number(event['calculated_volume']),
            str(len(event.get('markets', [])))
        )

    console.print(events_table)

    # Top Series Table
    console.print(f"\n[bold cyan]TOP {top_n} SERIES BY VOLUME[/bold cyan]\n")
    series_table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
    series_table.add_column("#", justify="right", style="dim", width=3)
    series_table.add_column("Series", style="white", max_width=45)
    series_table.add_column("Category", style="cyan", no_wrap=True)
    series_table.add_column("Frequency", style="blue", no_wrap=True)
    series_table.add_column("Volume", justify="right", style="yellow")

    all_series = []
    for series_list in snapshot['series_by_category'].values():
        all_series.extend(series_list)
    all_series.sort(key=lambda x: x.get('volume', 0), reverse=True)

    for i, series in enumerate(all_series[:top_n], 1):
        title = series.get('title', 'Unknown')
        if len(title) > 45:
            title = title[:42] + "..."

        series_table.add_row(
            str(i),
            title,
            series.get('category', 'Unknown'),
            series.get('frequency', 'Unknown'),
            format_number(series.get('volume', 0))
        )

    console.print(series_table)
    console.print()


def display_plain(snapshot: Dict[str, Any], top_n: int = 25):
    """Plain text output for when rich is not available."""
    meta = snapshot['metadata']

    print("=" * 80)
    print("KALSHI PLATFORM SNAPSHOT")
    print("=" * 80)
    print(f"Timestamp: {meta['timestamp']}")
    print(f"Total Series: {meta['total_series']:,}")
    print(f"Total Events: {meta['total_events']:,}")
    print(f"Events After Filter (≥{meta['min_volume_filter']:,}): {meta['events_after_filter']:,}")
    print(f"Total Volume: {meta['total_volume']:,} contracts")
    print(f"Categories: {len(meta['categories'])}")
    print()

    print("CATEGORY STATISTICS")
    print("-" * 80)
    stats = snapshot['category_statistics']
    sorted_cats = sorted(stats.items(), key=lambda x: x[1]['total_volume'], reverse=True)

    for category, cat_stats in sorted_cats:
        print(f"\n{category}:")
        print(f"  Events: {cat_stats['event_count']:,}")
        print(f"  Total Volume: {cat_stats['total_volume']:,} contracts")
        print(f"  Avg/Event: {cat_stats['avg_volume']:,.0f} contracts")

    print("\n" + "=" * 80)
    print(f"TOP {top_n} EVENTS BY VOLUME")
    print("-" * 80)

    all_events = []
    for events_list in snapshot['events_by_category'].values():
        all_events.extend(events_list)
    all_events.sort(key=lambda x: x['calculated_volume'], reverse=True)

    for i, event in enumerate(all_events[:top_n], 1):
        print(f"\n{i}. {event.get('title', 'Unknown')}")
        print(f"   Ticker: {event.get('event_ticker', 'N/A')} | "
              f"Category: {event.get('category', 'Unknown')}")
        print(f"   Volume: {event['calculated_volume']:,} contracts | "
              f"Markets: {len(event.get('markets', []))}")


def format_csv(snapshot: Dict[str, Any]) -> str:
    """Format snapshot as CSV."""
    lines = ["# EVENTS", "event_ticker,title,category,volume,market_count,series_ticker"]

    all_events = []
    for events_list in snapshot['events_by_category'].values():
        all_events.extend(events_list)
    all_events.sort(key=lambda x: x['calculated_volume'], reverse=True)

    for event in all_events:
        lines.append(
            f"{event.get('event_ticker', '')},"
            f"\"{event.get('title', '').replace(',', ';')}\","
            f"{event.get('category', '')},"
            f"{event['calculated_volume']},"
            f"{len(event.get('markets', []))},"
            f"{event.get('series_ticker', '')}"
        )

    lines.extend(["\n# SERIES", "ticker,title,category,frequency,volume,tags"])

    all_series = []
    for series_list in snapshot['series_by_category'].values():
        all_series.extend(series_list)
    all_series.sort(key=lambda x: x.get('volume', 0), reverse=True)

    for series in all_series:
        lines.append(
            f"{series.get('ticker', '')},"
            f"\"{series.get('title', '').replace(',', ';')}\","
            f"{series.get('category', '')},"
            f"{series.get('frequency', '')},"
            f"{series.get('volume', 0)},"
            f"\"{';'.join(series.get('tags', []))}\""
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Fetch and analyze Kalshi platform snapshot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='See script docstring for detailed documentation'
    )
    parser.add_argument(
        '--output-format',
        choices=['json', 'csv', 'console'],
        default='console',
        help='Output format (default: console)'
    )
    parser.add_argument(
        '--min-volume',
        type=int,
        default=50000,
        help='Minimum volume filter for events (default: 50000)'
    )
    parser.add_argument(
        '--status',
        choices=['open', 'closed', 'settled'],
        default='open',
        help='Event status filter (default: open)'
    )
    parser.add_argument(
        '--output-file', '-o',
        help='Output file path (default: stdout)'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        default=25,
        help='Number of top events/series to show (default: 25)'
    )

    args = parser.parse_args()

    try:
        client = KalshiSnapshot()
        series = client.get_all_series(include_volume=True)
        events = client.get_all_events(status=args.status, with_nested_markets=True)
        snapshot = client.analyze_snapshot(series, events, min_volume=args.min_volume)

        # Generate output
        if args.output_format == 'json':
            output = json.dumps(snapshot, indent=2)
        elif args.output_format == 'csv':
            output = format_csv(snapshot)
        else:  # console
            if args.output_file:
                # If saving to file, use plain text
                import io
                buf = io.StringIO()
                old_stdout = sys.stdout
                sys.stdout = buf
                display_plain(snapshot, args.top_n)
                sys.stdout = old_stdout
                output = buf.getvalue()
            else:
                # Display to terminal with rich if available
                if RICH_AVAILABLE:
                    display_with_rich(snapshot, args.top_n)
                else:
                    display_plain(snapshot, args.top_n)
                return 0

        # Write output if file specified
        if args.output_file:
            with open(args.output_file, 'w') as f:
                f.write(output)
            print(f"✓ Snapshot saved to {args.output_file}", file=sys.stderr)
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
