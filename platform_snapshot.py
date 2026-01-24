#!/usr/bin/env python3
"""
Kalshi Platform Snapshot Script
Level 1: Platform Crawler

Purpose: Discover what exists on the platform and what's actually being traded.
Fetches all series and events, groups by category, and sorts by volume.

Usage:
    python platform_snapshot.py [--output-format json|csv|console] [--min-volume MIN]
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
    print("Error: 'requests' library not found. Install with: pip install requests")
    sys.exit(1)


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
        """
        Fetch all series from the platform.

        Args:
            include_volume: If True, includes total volume traded across all events in each series

        Returns:
            List of series dictionaries
        """
        print("Fetching all series...", file=sys.stderr)
        params = {'include_volume': str(include_volume).lower()}

        data = self._get('series', params=params)
        series_list = data.get('series', [])

        print(f"Found {len(series_list)} series", file=sys.stderr)
        return series_list

    def get_all_events(
        self,
        status: str = 'open',
        with_nested_markets: bool = True,
        min_close_ts: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch all events from the platform with pagination support.

        Args:
            status: Filter by event status ('open', 'closed', 'settled')
            with_nested_markets: Include market data within events
            min_close_ts: Filter events with close time after this Unix timestamp

        Returns:
            List of event dictionaries
        """
        print(f"Fetching all {status} events...", file=sys.stderr)

        all_events = []
        cursor = None
        page = 1

        while True:
            params = {
                'limit': 200,  # Maximum allowed
                'status': status,
                'with_nested_markets': str(with_nested_markets).lower()
            }

            if cursor:
                params['cursor'] = cursor
            if min_close_ts:
                params['min_close_ts'] = min_close_ts

            data = self._get('events', params=params)
            events = data.get('events', [])

            if not events:
                break

            all_events.extend(events)
            print(f"  Page {page}: fetched {len(events)} events (total: {len(all_events)})",
                  file=sys.stderr)

            # Check for next page
            cursor = data.get('cursor', '')
            if not cursor:
                break

            page += 1

        print(f"Total events fetched: {len(all_events)}", file=sys.stderr)
        return all_events

    def analyze_snapshot(
        self,
        series: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
        min_volume: int = 0
    ) -> Dict[str, Any]:
        """
        Analyze and organize snapshot data.

        Args:
            series: List of series data
            events: List of events data
            min_volume: Minimum volume threshold for filtering

        Returns:
            Dictionary with organized snapshot data
        """
        print(f"Analyzing snapshot data (min_volume={min_volume})...", file=sys.stderr)

        # Group series by category
        series_by_category = {}
        for s in series:
            category = s.get('category', 'Unknown')
            if category not in series_by_category:
                series_by_category[category] = []
            series_by_category[category].append(s)

        # Sort series within each category by volume
        for category in series_by_category:
            series_by_category[category].sort(
                key=lambda x: x.get('volume', 0),
                reverse=True
            )

        # Group events by category
        events_by_category = {}
        total_volume = 0

        for event in events:
            category = event.get('category', 'Unknown')
            if category not in events_by_category:
                events_by_category[category] = []

            # Calculate total volume from nested markets
            event_volume = 0
            markets = event.get('markets', [])
            for market in markets:
                market_vol = market.get('volume', 0)
                event_volume += market_vol

            event['calculated_volume'] = event_volume
            total_volume += event_volume

            # Filter by minimum volume
            if event_volume >= min_volume:
                events_by_category[category].append(event)

        # Sort events within each category by volume
        for category in events_by_category:
            events_by_category[category].sort(
                key=lambda x: x.get('calculated_volume', 0),
                reverse=True
            )

        # Generate summary statistics
        category_stats = {}
        for category, events_list in events_by_category.items():
            total_cat_volume = sum(e.get('calculated_volume', 0) for e in events_list)
            category_stats[category] = {
                'event_count': len(events_list),
                'total_volume': total_cat_volume,
                'avg_volume_per_event': total_cat_volume / len(events_list) if events_list else 0
            }

        return {
            'metadata': {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'total_series': len(series),
                'total_events': len(events),
                'events_after_filter': sum(len(v) for v in events_by_category.values()),
                'total_volume': total_volume,
                'min_volume_filter': min_volume,
                'categories': list(events_by_category.keys())
            },
            'series_by_category': series_by_category,
            'events_by_category': events_by_category,
            'category_statistics': category_stats
        }


def format_console_output(snapshot: Dict[str, Any]) -> str:
    """Format snapshot data for console display."""
    lines = []
    metadata = snapshot['metadata']

    lines.append("=" * 80)
    lines.append("KALSHI PLATFORM SNAPSHOT")
    lines.append("=" * 80)
    lines.append(f"Timestamp: {metadata['timestamp']}")
    lines.append(f"Total Series: {metadata['total_series']}")
    lines.append(f"Total Events: {metadata['total_events']}")
    lines.append(f"Events After Filter (min_volume={metadata['min_volume_filter']}): {metadata['events_after_filter']}")
    lines.append(f"Total Platform Volume: {metadata['total_volume']:,} contracts")
    lines.append(f"Categories: {len(metadata['categories'])}")
    lines.append("")

    # Category Statistics
    lines.append("CATEGORY STATISTICS (sorted by volume)")
    lines.append("-" * 80)
    stats = snapshot['category_statistics']
    sorted_cats = sorted(stats.items(), key=lambda x: x[1]['total_volume'], reverse=True)

    for category, cat_stats in sorted_cats:
        lines.append(f"\n{category}:")
        lines.append(f"  Events: {cat_stats['event_count']}")
        lines.append(f"  Total Volume: {cat_stats['total_volume']:,} contracts")
        lines.append(f"  Avg Volume/Event: {cat_stats['avg_volume_per_event']:.0f} contracts")

    # Top Events by Volume (across all categories)
    lines.append("\n" + "=" * 80)
    lines.append("TOP 20 EVENTS BY VOLUME")
    lines.append("-" * 80)

    all_events = []
    for events_list in snapshot['events_by_category'].values():
        all_events.extend(events_list)

    all_events.sort(key=lambda x: x.get('calculated_volume', 0), reverse=True)

    for i, event in enumerate(all_events[:20], 1):
        title = event.get('title', 'Unknown')
        ticker = event.get('event_ticker', 'N/A')
        volume = event.get('calculated_volume', 0)
        category = event.get('category', 'Unknown')
        market_count = len(event.get('markets', []))

        lines.append(f"\n{i}. {title}")
        lines.append(f"   Ticker: {ticker} | Category: {category}")
        lines.append(f"   Volume: {volume:,} contracts | Markets: {market_count}")

    # Top Series by Volume
    lines.append("\n" + "=" * 80)
    lines.append("TOP 20 SERIES BY VOLUME")
    lines.append("-" * 80)

    all_series = []
    for series_list in snapshot['series_by_category'].values():
        all_series.extend(series_list)

    all_series.sort(key=lambda x: x.get('volume', 0), reverse=True)

    for i, series in enumerate(all_series[:20], 1):
        title = series.get('title', 'Unknown')
        ticker = series.get('ticker', 'N/A')
        volume = series.get('volume', 0)
        category = series.get('category', 'Unknown')
        frequency = series.get('frequency', 'Unknown')

        lines.append(f"\n{i}. {title}")
        lines.append(f"   Ticker: {ticker} | Category: {category} | Frequency: {frequency}")
        lines.append(f"   Total Volume: {volume:,} contracts")

    lines.append("\n" + "=" * 80)

    return "\n".join(lines)


def format_csv_output(snapshot: Dict[str, Any]) -> str:
    """Format snapshot data as CSV."""
    lines = []

    # Events CSV
    lines.append("# EVENTS")
    lines.append("event_ticker,title,category,volume,market_count,series_ticker")

    all_events = []
    for events_list in snapshot['events_by_category'].values():
        all_events.extend(events_list)

    all_events.sort(key=lambda x: x.get('calculated_volume', 0), reverse=True)

    for event in all_events:
        ticker = event.get('event_ticker', '')
        title = event.get('title', '').replace(',', ';')
        category = event.get('category', '')
        volume = event.get('calculated_volume', 0)
        market_count = len(event.get('markets', []))
        series_ticker = event.get('series_ticker', '')

        lines.append(f"{ticker},{title},{category},{volume},{market_count},{series_ticker}")

    # Series CSV
    lines.append("\n# SERIES")
    lines.append("ticker,title,category,frequency,volume,tags")

    all_series = []
    for series_list in snapshot['series_by_category'].values():
        all_series.extend(series_list)

    all_series.sort(key=lambda x: x.get('volume', 0), reverse=True)

    for series in all_series:
        ticker = series.get('ticker', '')
        title = series.get('title', '').replace(',', ';')
        category = series.get('category', '')
        frequency = series.get('frequency', '')
        volume = series.get('volume', 0)
        tags = '|'.join(series.get('tags', []))

        lines.append(f"{ticker},{title},{category},{frequency},{volume},{tags}")

    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Fetch and analyze Kalshi platform snapshot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
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
        default=0,
        help='Minimum volume filter for events (default: 0)'
    )
    parser.add_argument(
        '--status',
        choices=['open', 'closed', 'settled'],
        default='open',
        help='Event status filter (default: open)'
    )
    parser.add_argument(
        '--output-file',
        '-o',
        help='Output file path (default: stdout)'
    )

    args = parser.parse_args()

    try:
        # Initialize client
        client = KalshiSnapshot()

        # Fetch data
        series = client.get_all_series(include_volume=True)
        events = client.get_all_events(status=args.status, with_nested_markets=True)

        # Analyze
        snapshot = client.analyze_snapshot(series, events, min_volume=args.min_volume)

        # Format output
        if args.output_format == 'json':
            output = json.dumps(snapshot, indent=2)
        elif args.output_format == 'csv':
            output = format_csv_output(snapshot)
        else:  # console
            output = format_console_output(snapshot)

        # Write output
        if args.output_file:
            with open(args.output_file, 'w') as f:
                f.write(output)
            print(f"Snapshot saved to {args.output_file}", file=sys.stderr)
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
