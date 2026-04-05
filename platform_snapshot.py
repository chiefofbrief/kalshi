#!/usr/bin/env python3
"""
Kalshi Platform Snapshot Script - Market Discovery & Screening Tool

PURPOSE:
    Discover actionable trading opportunities on the Kalshi prediction market platform.
    Identifies high-liquidity markets, filters out "ghost towns," and surfaces opportunities
    for manual trading strategies (certainty gaps, fresh markets, closing urgency, etc.).

WHAT IT DOES:
    - Fetches all series and events from the Kalshi API (public, no auth needed)
    - Handles pagination automatically (4000+ events across multiple pages)
    - Calculates price ranges, 24h volume, open interest for each event
    - Filters by volume, price range, and category
    - Sorts by close date (urgency), creation date (freshness), or volume
    - Displays beautiful terminal tables with actionable metrics
    - Optionally exports to JSON/CSV for deeper analysis

DEFAULT BEHAVIOR:
    python platform_snapshot.py

    Filters: min_volume=50000, max_price=97¢ (excludes "already decided" markets)
    Sorts: closing-soon (markets closing soonest first - actionable urgency)
    Shows: Platform overview, category stats, top 25 events, series rankings
           Deep-dive sections for: Economics, Financials, Companies

USAGE EXAMPLES:

    BASIC FILTERING:
    ----------------
    # See more markets (lower volume threshold)
    python platform_snapshot.py --min-volume 10000

    # See everything (warning: 4000+ events!)
    python platform_snapshot.py --min-volume 0

    # Include "already decided" markets (>97¢)
    python platform_snapshot.py --max-price 100

    # Focus on "certainty gap" opportunities (Strategy 1: 90-97¢ range)
    python platform_snapshot.py --min-price 90 --max-price 97

    # Exclude high-confidence markets (focus on uncertain outcomes)
    python platform_snapshot.py --max-price 90

    SORTING OPTIONS:
    ----------------
    # Markets closing soonest (default - actionable urgency)
    python platform_snapshot.py --sort closing-soon

    # Fresh opportunities (newly created markets)
    python platform_snapshot.py --sort new

    # Current momentum (highest 24h volume)
    python platform_snapshot.py --sort hot-24h

    # Historical popularity (total volume)
    python platform_snapshot.py --sort volume

    CATEGORY FILTERING:
    -------------------
    # Show only Economics markets (all of them, not just top 25)
    python platform_snapshot.py --category Economics

    # Show only Financials markets
    python platform_snapshot.py --category Financials

    # Combine with other filters
    python platform_snapshot.py --category Politics --sort closing-soon --min-price 90

    DATA EXPORT:
    ------------
    # Export full data to JSON for analysis
    python platform_snapshot.py --output-format json -o snapshot.json

    # Export to CSV for spreadsheet analysis
    python platform_snapshot.py --output-format csv -o markets.csv

    # Save console output to file
    python platform_snapshot.py -o snapshot.txt

    OTHER OPTIONS:
    --------------
    # Fetch closed or settled events instead of open
    python platform_snapshot.py --status closed

    # Show top 50 events instead of 25
    python platform_snapshot.py --top-n 50

FULL PARAMETER REFERENCE:
    --min-volume INT       Minimum volume threshold (default: 50000)
                          Lower values show more markets but include low-liquidity events
                          Use 0 to see everything

    --max-price CENTS      Maximum price filter in cents (default: 97)
                          Excludes markets where ANY market in the event exceeds this price
                          Use 100 to see everything including "already decided" markets
                          Use 90 to focus only on uncertain outcomes

    --min-price CENTS      Minimum price filter in cents (default: 0)
                          Only shows events where at least one market meets this threshold
                          Combine with --max-price for range filtering (e.g., 90-97¢)

    --sort MODE           Sort order for events (default: closing-soon)
                          Options:
                            closing-soon: Markets closing soonest first (temporal urgency)
                            new: Recently created markets (fresh opportunities)
                            hot-24h: Highest 24-hour volume (current momentum)
                            volume: Total historical volume (popularity)

    --category NAME       Filter to single category (shows ALL events in that category)
                          Common categories: Economics, Politics, Sports, Financials,
                          Companies, Entertainment, Crypto, Elections, etc.

    --status STATUS       Event status filter (default: open)
                          Options: open, closed, settled

    --output-format FMT   Output format (default: console)
                          Options: console, json, csv

    --output-file PATH    Save output to file instead of stdout
    -o PATH              (short form)

    --top-n INT          Number of top events/series to show (default: 25)
                          Only applies to general overview, not category filtering

API ENDPOINTS USED:
    GET /series           - All series with volume data
    GET /events           - All events with pagination (200 per page)
                           Using with_nested_markets=true to get market-level data

    Both are public endpoints (no authentication required)

INSTALLATION:
    pip install requests rich

EXAMPLE OUTPUT:
    Platform Summary: 8,104 series, 4,050 events, 764M contracts
    After filter (≥50k volume, ≤97¢): 456 events across 14 categories

    Category Stats: Sports (395M), Politics (222M), Economics (39M)

    Events Table Columns:
    - Event: Title of the event
    - Category: Market category
    - Age: Time since event was created (e.g., "2d", "1w", "3mo")
    - Close: Time until market closes (e.g., "6d", "2w", "Closed")
    - Volume: Total historical volume
    - Vol 24h: Volume in last 24 hours
    - Open Int: Current open interest (active positions)
    - Price Range: Min-Max prices across all markets in event
      * "$0.92-$0.99" = likely winner is clear (certainty gap opportunity)
      * "$0.35-$0.65" = uncertain outcome (value bet opportunity)
    - Mkts: Number of markets in this event

TRADING STRATEGIES SUPPORTED:

    Strategy 1: Certainty Gap (90-97¢)
        python platform_snapshot.py --min-price 90 --max-price 97
        Find markets priced 90-97¢ with room to run to 99¢

    Strategy 2: Fresh Opportunities
        python platform_snapshot.py --sort new
        Get in before market reaches consensus

    Strategy 3: Closing Urgency
        python platform_snapshot.py --sort closing-soon
        Focus on markets needing decisions soon (faster capital turnover)

    Strategy 4: Domain Expertise
        python platform_snapshot.py --category Economics
        Focus on your area of expertise

    Strategy 5: Hot Markets
        python platform_snapshot.py --sort hot-24h
        Find where current trading activity is happening

NEXT STEPS:
    After identifying opportunities in this screener:
    1. Drill down into specific events: GET /events/{ticker}
    2. Review market rules and settlement sources
    3. Check order book depth: GET /market/{ticker}/orderbook
    4. Place trades manually or build automation
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
        min_volume: int = 0,
        min_price: int = 0,
        max_price: int = 100,
        category_filter: Optional[str] = None,
        sort_by: str = 'closing-soon'
    ) -> Dict[str, Any]:
        """
        Analyze and organize snapshot data with filtering and sorting.

        Args:
            series: List of series data
            events: List of events data
            min_volume: Minimum volume threshold
            min_price: Minimum price in cents (0-100)
            max_price: Maximum price in cents (0-100)
            category_filter: Filter to specific category (None = all)
            sort_by: Sort method (closing-soon, new, hot-24h, volume)

        Returns:
            Dictionary with organized snapshot data
        """
        filters_desc = f"min_volume={min_volume:,}, price_range={min_price}-{max_price}¢"
        if category_filter:
            filters_desc += f", category={category_filter}"
        print(f"Analyzing snapshot ({filters_desc})...", file=sys.stderr)

        # Enrich each event with calculated metrics
        for event in events:
            markets = event.get('markets', [])

            # Calculate total volume
            event_volume = sum(float(m.get('volume_fp', m.get('volume', 0))) for m in markets)
            event['calculated_volume'] = int(event_volume)

            # Calculate 24h volume
            volume_24h = sum(float(m.get('volume_24h_fp', m.get('volume_24h', 0))) for m in markets)
            event['calculated_volume_24h'] = int(volume_24h)

            # Calculate open interest
            open_interest = sum(float(m.get('open_interest_fp', m.get('open_interest', 0))) for m in markets)
            event['calculated_open_interest'] = int(open_interest)

            # Calculate price range and ME sums (Bid/Ask/Last)
            prices = []
            bid_sum = 0
            ask_sum = 0
            outcome_names = []
            
            for m in markets:
                # Last Price
                price_str = m.get('last_price_dollars') or m.get('yes_bid_dollars', '0')
                try:
                    price_cents = int(float(price_str) * 100)
                    prices.append(price_cents)
                except (ValueError, TypeError):
                    pass
                
                # Order Book
                try:
                    bid_sum += int(float(m.get('yes_bid_dollars', 0)) * 100)
                    ask_sum += int(float(m.get('yes_ask_dollars', 0)) * 100)
                except (ValueError, TypeError):
                    pass
                
                # Outcome Name
                name = m.get('yes_sub_title') or m.get('subtitle') or m.get('ticker')
                if name:
                    outcome_names.append(name)

            if prices:
                event['price_min'] = min(prices)
                event['price_max'] = max(prices)
                if event.get('mutually_exclusive', False):
                    event['sum_yes_cents'] = sum(prices)
                    event['sum_yes_bid'] = bid_sum
                    event['sum_yes_ask'] = ask_sum
                    event['outcomes'] = outcome_names
                else:
                    event['sum_yes_cents'] = None
                    event['sum_yes_bid'] = None
                    event['sum_yes_ask'] = None
            else:
                event['price_min'] = 0
                event['price_max'] = 0
                event['sum_yes_cents'] = None

            # Get close time for sorting
            close_times = []
            future_close_times = []
            now = datetime.now(timezone.utc)
            
            for m in markets:
                close_time_str = m.get('close_time')
                if close_time_str:
                    try:
                        ct_clean = close_time_str.replace('Z', '+00:00')
                        close_dt = datetime.fromisoformat(ct_clean)
                        close_times.append(close_dt)
                        if close_dt > now:
                            future_close_times.append(close_dt)
                    except (ValueError, TypeError):
                        continue

            if future_close_times:
                event['closest_close_time'] = min(future_close_times)
                event['is_actionable'] = True
            elif close_times:
                event['closest_close_time'] = min(close_times)
                event['is_actionable'] = False
            else:
                event['closest_close_time'] = datetime.max.replace(tzinfo=timezone.utc)
                event['is_actionable'] = False

            # Get creation time for sorting - Use open_time for better accuracy
            open_time_str = markets[0].get('open_time') if markets else None
            if open_time_str:
                try:
                    event['created_time'] = datetime.fromisoformat(open_time_str.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    event['created_time'] = datetime.min.replace(tzinfo=timezone.utc)
            else:
                event['created_time'] = datetime.min.replace(tzinfo=timezone.utc)

        # Group and sort series by category
        series_by_category = {}
        for s in series:
            category = s.get('category', 'Unknown')
            series_by_category.setdefault(category, []).append(s)

        for category in series_by_category:
            series_by_category[category].sort(key=lambda x: x.get('volume', 0), reverse=True)

        # Filter and group events
        events_by_category = {}
        total_volume = sum(e['calculated_volume'] for e in events)
        filtered_count = 0

        for event in events:
            # Apply filters
            if not event.get('is_actionable', False):
                continue
            
            if event['calculated_volume'] < min_volume:
                continue

            # Price filter: event must have at least one market in range
            if event['price_max'] > max_price:
                continue
            if event['price_min'] < min_price and event['price_max'] < min_price:
                continue

            # Category filter
            event_category = event.get('category', 'Unknown')
            if category_filter and event_category != category_filter:
                continue

            events_by_category.setdefault(event_category, []).append(event)
            filtered_count += 1

        # Sort events within each category based on sort_by parameter
        sort_key_map = {
            'closing-soon': lambda x: x['closest_close_time'],
            'new': lambda x: x['created_time'],
            'hot-24h': lambda x: x['calculated_volume_24h'],
            'volume': lambda x: x['calculated_volume']
        }

        sort_key_func = sort_key_map.get(sort_by, sort_key_map['closing-soon'])
        sort_reverse = sort_by in ['hot-24h', 'volume']  # Descending for volume, ascending for time

        for category in events_by_category:
            events_by_category[category].sort(key=sort_key_func, reverse=sort_reverse)

        # Generate category statistics
        category_stats = {}
        for category, events_list in events_by_category.items():
            total_cat_volume = sum(e['calculated_volume'] for e in events_list)
            category_stats[category] = {
                'event_count': len(events_list),
                'total_volume': total_cat_volume,
                'avg_volume': total_cat_volume / len(events_list) if events_list else 0
            }

        # Identify signals across 5 strategies (ONLY for the 7 core categories)
        signals = {
            'closing_urgency': [],
            'certainty_gaps': [],
            'arbitrage': [],
            'momentum': [],
            'fresh_alpha': []
        }
        
        now = datetime.now(timezone.utc)
        core_categories = ['Economics', 'Financials', 'Companies', 'Politics', 'Elections', 'Science and Technology', 'Crypto']
        all_filtered_events = []
        for cat in core_categories:
            if cat in events_by_category:
                all_filtered_events.extend(events_by_category[cat])
            
        for e in all_filtered_events:
            # 1. Closing Urgency (< 48h, high volume relative to category)
            delta = e['closest_close_time'] - now
            if delta.total_seconds() > 0 and delta.days < 2 and e['calculated_volume'] > 10000:
                signals['closing_urgency'].append(e)
                
            # 2. Certainty Gaps (85-97c)
            if 85 <= e['price_max'] <= 97 and e['calculated_volume'] > 20000:
                signals['certainty_gaps'].append(e)
                
            # 3. Arbitrage (Triggered by Order Book)
            if e.get('sum_yes_bid') is not None:
                # Real Sell Arb (Sum of Bids > 100)
                # Real Buy Arb (Sum of Asks < 100)
                if e['sum_yes_bid'] > 100 or e['sum_yes_ask'] < 100:
                    signals['arbitrage'].append(e)
                # Also include major Last Price deviations for context (> 5c)
                elif abs(e['sum_yes_cents'] - 100) >= 5:
                    signals['arbitrage'].append(e)
                
            # 4. Momentum (Top 24h volume) - we'll sort after
            if e['calculated_volume_24h'] > 5000:
                signals['momentum'].append(e)
                
            # 5. Fresh Alpha (New in last 48h)
            created_delta = now - e['created_time']
            if created_delta.days < 2 and created_delta.days >= 0:
                signals['fresh_alpha'].append(e)

        # Sort and limit signals
        signals['closing_urgency'].sort(key=lambda x: x['closest_close_time'])
        # Certainty Gaps: Priority to Closing Soonest
        signals['certainty_gaps'].sort(key=lambda x: x['closest_close_time'])
        signals['arbitrage'].sort(key=lambda x: max(abs(x.get('sum_yes_bid', 100) - 100), abs(x.get('sum_yes_ask', 100) - 100)), reverse=True)
        signals['momentum'].sort(key=lambda x: x['calculated_volume_24h'], reverse=True)
        signals['fresh_alpha'].sort(key=lambda x: x['created_time'], reverse=True)

        # Limit all except certainty gaps
        signals['closing_urgency'] = signals['closing_urgency'][:10]
        signals['arbitrage'] = signals['arbitrage'][:10]
        signals['momentum'] = signals['momentum'][:10]
        signals['fresh_alpha'] = signals['fresh_alpha'][:10]
        # certainty_gaps remains unlimited per request

        print(f"✓ Analysis complete: {filtered_count} events after filters", file=sys.stderr)

        return {
            'metadata': {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'total_series': len(series),
                'total_events': len(events),
                'events_after_filter': sum(len(v) for v in events_by_category.values()),
                'total_volume': total_volume,
                'min_volume_filter': min_volume,
                'min_price_filter': min_price,
                'max_price_filter': max_price,
                'category_filter': category_filter,
                'sort_by': sort_by,
                'categories': sorted(events_by_category.keys())
            },
            'series_by_category': series_by_category,
            'events_by_category': events_by_category,
            'category_statistics': category_stats,
            'signals': signals
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


def format_price_range(min_cents: int, max_cents: int) -> str:
    """Format price range as dollar string."""
    if min_cents == 0 and max_cents == 0:
        return "N/A"
    return f"${min_cents/100:.2f}-${max_cents/100:.2f}"


def format_close_date(close_dt: datetime) -> str:
    """Format close datetime as readable string."""
    if close_dt.year >= 9999:
        return "Unknown"
    now = datetime.now(timezone.utc)
    # Ensure both are timezone aware for comparison
    if close_dt.tzinfo is None:
        close_dt = close_dt.replace(tzinfo=timezone.utc)
        
    delta = close_dt - now

    if delta.total_seconds() < 0:
        return "Closed"
    elif delta.days == 0:
        hours = int(delta.total_seconds() // 3600)
        return f"{hours}h"
    elif delta.days < 7:
        return f"{delta.days}d"
    elif delta.days < 30:
        weeks = delta.days // 7
        return f"{weeks}w"
    else:
        months = delta.days // 30
        return f"{months}mo"


def format_age(created_dt: datetime) -> str:
    """Format event age (time since creation) as readable string."""
    if created_dt.year <= 1:
        return "N/A"
    now = datetime.now(timezone.utc)
    # Ensure both are timezone aware for comparison
    if created_dt.tzinfo is None:
        created_dt = created_dt.replace(tzinfo=timezone.utc)
        
    delta = now - created_dt

    if delta.days == 0:
        hours = delta.seconds // 3600
        if hours == 0:
            return "<1h"
        return f"{hours}h"
    elif delta.days < 7:
        return f"{delta.days}d"
    elif delta.days < 30:
        weeks = delta.days // 7
        return f"{weeks}w"
    elif delta.days < 365:
        months = delta.days // 30
        return f"{months}mo"
    else:
        years = delta.days // 365
        return f"{years}y"


def create_events_table(events: List[Dict[str, Any]], title: str, console: Console, limit: Optional[int] = None):
    """Helper to create events table with standardized columns."""
    events_table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta", expand=True)
    events_table.add_column("#", justify="right", style="dim", width=3)
    events_table.add_column("Event", style="white", width=33, no_wrap=False)
    events_table.add_column("Event Ticker", style="yellow", width=14)
    events_table.add_column("Category", style="cyan", width=10)
    events_table.add_column("Age", style="dim", width=4)
    events_table.add_column("Close", style="blue", width=5)
    events_table.add_column("Volume", justify="right", style="yellow", width=7)
    events_table.add_column("Vol 24h", justify="right", style="yellow", width=7)
    events_table.add_column("Open Int", justify="right", style="green", width=7)
    events_table.add_column("Price Range", justify="center", style="magenta", width=13)
    events_table.add_column("Mkts", justify="right", style="dim", width=4)

    display_events = events[:limit] if limit else events

    for i, event in enumerate(display_events, 1):
        title_str = event.get('title', 'Unknown')
        if title_str and len(title_str) > 40:
            title_str = title_str[:37] + "..."

        # Ensure we have a title
        if not title_str:
            title_str = "[No Title]"

        event_ticker = event.get('event_ticker', '')

        events_table.add_row(
            str(i),
            title_str,
            event_ticker,
            event.get('category', 'Unknown')[:10],
            format_age(event.get('created_time', datetime.min.replace(tzinfo=None))),
            format_close_date(event.get('closest_close_time', datetime.max.replace(tzinfo=None))),
            format_number(event['calculated_volume']),
            format_number(event['calculated_volume_24h']),
            format_number(event['calculated_open_interest']),
            format_price_range(event['price_min'], event['price_max']),
            str(len(event.get('markets', [])))
        )

    console.print(f"\n[bold cyan]{title}[/bold cyan]\n")
    console.print(events_table)


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

    # Show active filters
    filters_text = f"Filters: volume≥{meta['min_volume_filter']:,}, price={meta['min_price_filter']}-{meta['max_price_filter']}¢"
    if meta.get('category_filter'):
        filters_text += f", category={meta['category_filter']}"
    header.append(filters_text + "\n", style="dim")

    header.append(f"After filters: ", style="bold")
    header.append(f"{meta['events_after_filter']:,} events across {len(meta['categories'])} categories\n")
    header.append(f"Sort: {meta['sort_by']}", style="dim")

    console.print(Panel(header, border_style="cyan"))

    # Category Statistics Table (unless filtering by category)
    if not meta.get('category_filter'):
        console.print("\n[bold cyan]CATEGORY STATISTICS[/bold cyan]\n")
        cat_table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta", expand=True)
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

    # Main events table
    priority_categories = ['Economics', 'Financials', 'Companies', 'Politics', 'Elections', 'Science and Technology', 'Crypto']
    
    # Filter to only the core 7 categories
    filtered_events_by_cat = {cat: snapshot['events_by_category'].get(cat, []) for cat in priority_categories}
    
    # Gather all events in sorted order
    all_events = []
    for cat in priority_categories:
        all_events.extend(filtered_events_by_cat[cat])

    # Re-sort all events by the chosen sort method (they're already sorted within categories)
    sort_key_map = {
        'closing-soon': lambda x: x.get('closest_close_time', datetime.max.replace(tzinfo=None)),
        'new': lambda x: x.get('created_time', datetime.min.replace(tzinfo=None)),
        'hot-24h': lambda x: x.get('calculated_volume_24h', 0),
        'volume': lambda x: x.get('calculated_volume', 0)
    }
    sort_key_func = sort_key_map.get(meta['sort_by'], sort_key_map['closing-soon'])
    sort_reverse = meta['sort_by'] in ['hot-24h', 'volume']
    all_events.sort(key=sort_key_func, reverse=sort_reverse)

    # Main events table (if not category filtering, show top N; if category filtering, show all)
    if meta.get('category_filter'):
        table_title = f"ALL {meta['category_filter'].upper()} EVENTS (sorted by {meta['sort_by']})"
        create_events_table(all_events, table_title, console, limit=None)
    else:
        table_title = f"TOP {top_n} EVENTS (sorted by {meta['sort_by']})"
        create_events_table(all_events, table_title, console, limit=top_n)

        # Deep-dive sections for key categories
        priority_categories = ['Economics', 'Financials', 'Companies']
        for cat in priority_categories:
            cat_events = snapshot['events_by_category'].get(cat, [])
            if cat_events:
                create_events_table(
                    cat_events,
                    f"{cat.upper()} MARKETS (sorted by {meta['sort_by']})",
                    console,
                    limit=15  # Show top 15 per category
                )

    # Top Series Table (only if not category filtering)
    if not meta.get('category_filter'):
        console.print(f"\n[bold cyan]TOP {top_n} SERIES BY VOLUME[/bold cyan]\n")
        series_table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta", expand=True)
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


def format_markdown(snapshot: Dict[str, Any], top_n: int = 25) -> str:
    """Format snapshot as a vertical Markdown document for readability."""
    meta = snapshot['metadata']
    lines = []
    
    lines.append(f"# Kalshi Platform Snapshot")
    lines.append(f"**Timestamp:** {meta['timestamp']}")
    lines.append(f"**Platform:** {meta['total_series']:,} series, {meta['total_events']:,} events, {format_number(meta['total_volume'])} contracts")
    lines.append(f"**Filters:** Volume ≥ {meta['min_volume_filter']:,}, Price {meta['min_price_filter']}-{meta['max_price_filter']}¢")
    lines.append(f"**Sort:** {meta['sort_by']}")
    lines.append("")

    # --- TOP TRADING SIGNALS SECTION ---
    lines.append("## 🚀 TOP TRADING SIGNALS")
    
    signals = snapshot.get('signals', {})
    
    # 1. Arbitrage
    if signals.get('arbitrage'):
        # Only show real SELL arbs (Bids > 100) - mathematically guaranteed profit
        real_arbs = [e for e in signals['arbitrage'] if e.get('sum_yes_bid', 0) > 100]
        
        if real_arbs:
            lines.append("### ⚖️ Arbitrage Opportunities (Guaranteed SELL Arb)")
            for i, e in enumerate(real_arbs[:10], 1):
                # Use series_ticker for robust landing page link
                ticker = e.get('series_ticker') or e.get('event_ticker')
                # Kalshi series pages usually use the prefix (e.g., KXWTIW)
                url = f"https://kalshi.com/markets/{ticker.split('-')[0].lower()}"
                bid_sum = e.get('sum_yes_bid', 0)
                
                lines.append(f"{i}. **[{e['title']}]({url})** — `🔥 SELL ARB`")
                lines.append(f"   - **Order Book:** YES Bids Sum: `${bid_sum/100:.2f}`")
                lines.append(f"   - **The Play:** Sell the set (buy NO on all outcomes). Cost is < guaranteed payout.")
                lines.append(f"   - **Liquidity:** Vol: `{format_number(e['calculated_volume'])}` | Ticker: `{e['event_ticker']}`")
            lines.append("")

    # 2. Closing Urgency
    if signals.get('closing_urgency'):
        lines.append("### 🔴 Closing Soon (Temporal Urgency)")
        for i, e in enumerate(signals['closing_urgency'][:5], 1):
            ticker = e.get('series_ticker') or e.get('event_ticker')
            url = f"https://kalshi.com/markets/{ticker.split('-')[0].lower()}"
            lines.append(f"{i}. **[{e['title']}]({url})**")
            lines.append(f"   - **Closes in:** `{format_close_date(e['closest_close_time'])}` | **Volume:** `{format_number(e['calculated_volume'])}`")
            lines.append(f"   - **Price Range:** `{format_price_range(e['price_min'], e['price_max'])}`")
        lines.append("")

    # 3. Certainty Gaps
    if signals.get('certainty_gaps'):
        lines.append("### 🎯 Certainty Gaps (85-97¢)")
        for i, e in enumerate(signals['certainty_gaps'], 1):
            ticker = e.get('series_ticker') or e.get('event_ticker')
            url = f"https://kalshi.com/markets/{ticker.split('-')[0].lower()}"
            lines.append(f"{i}. **[{e['title']}]({url})**")
            lines.append(f"   - **Top Market:** `{e['price_max']}¢` | **Volume:** `{format_number(e['calculated_volume'])}`")
            lines.append(f"   - **Closes in:** `{format_close_date(e['closest_close_time'])}` | **Ticker:** `{e['event_ticker']}`")
        lines.append("")

    # 4. Momentum
    if signals.get('momentum'):
        lines.append("### 📈 Momentum (24h Volume)")
        for i, e in enumerate(signals['momentum'][:5], 1):
            ticker = e.get('series_ticker') or e.get('event_ticker')
            url = f"https://kalshi.com/markets/{ticker.split('-')[0].lower()}"
            lines.append(f"{i}. **[{e['title']}]({url})**")
            lines.append(f"   - **24h Vol:** `{format_number(e['calculated_volume_24h'])}` | **Price:** `{e['price_max']}¢`")
        lines.append("")
        
    lines.append("---")
    lines.append("")

    # Summary Table
    lines.append("## Category Summary")
    lines.append("| Category | Events | Volume | Avg/Event |")
    lines.append("| :--- | :---: | :---: | :---: |")
    
    core_categories = ['Economics', 'Financials', 'Companies', 'Politics', 'Elections', 'Science and Technology', 'Crypto']
    stats = snapshot['category_statistics']
    
    for category in core_categories:
        if category in stats:
            cat_stats = stats[category]
            lines.append(f"| {category} | {cat_stats['event_count']:,} | {format_number(cat_stats['total_volume'])} | {format_number(int(cat_stats['avg_volume']))} |")
    lines.append("")

    # Events by Category
    lines.append("## Detailed Events")
    
    core_categories = ['Economics', 'Financials', 'Companies', 'Politics', 'Elections', 'Science and Technology', 'Crypto']
    
    for category in core_categories:
        events = snapshot['events_by_category'].get(category, [])
        if not events:
            continue
            
        lines.append(f"### {category}")
        for i, event in enumerate(events[:top_n] if not meta.get('category_filter') else events, 1):
            created_dt = event.get('created_time', datetime.min.replace(tzinfo=None))
            close_dt = event.get('closest_close_time', datetime.max.replace(tzinfo=None))
            ticker = event.get('series_ticker') or event.get('event_ticker', 'N/A')
            url = f"https://kalshi.com/markets/{ticker.split('-')[0].lower()}"
            
            lines.append(f"#### {i}. [{event.get('title', 'Unknown')}]({url}) (`{event.get('event_ticker', 'N/A')}`)")
            lines.append(f"- **Price Range:** `{format_price_range(event['price_min'], event['price_max'])}`")
            lines.append(f"- **Timing:** Age: `{format_age(created_dt)}` | Closes in: `{format_close_date(close_dt)}`")
            lines.append(f"- **Liquidity:** Volume: `{format_number(event['calculated_volume'])}` (24h: `{format_number(event['calculated_volume_24h'])}`) | Open Interest: `{format_number(event['calculated_open_interest'])}`")
            lines.append(f"- **Structure:** {len(event.get('markets', []))} individual markets")
            lines.append("")
            
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Fetch and analyze Kalshi platform snapshot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='See script docstring for detailed documentation'
    )
    parser.add_argument(
        '--output-format',
        choices=['json', 'csv', 'console', 'md'],
        default='md',
        help='Output format (default: md)'
    )
    parser.add_argument(
        '--min-volume',
        type=int,
        default=50000,
        help='Minimum volume filter for events (default: 50000)'
    )
    parser.add_argument(
        '--max-price',
        type=int,
        default=97,
        help='Maximum price in cents - excludes events with any market above this (default: 97)'
    )
    parser.add_argument(
        '--min-price',
        type=int,
        default=0,
        help='Minimum price in cents - only shows events with at least one market above this (default: 0)'
    )
    parser.add_argument(
        '--sort',
        choices=['closing-soon', 'new', 'hot-24h', 'volume'],
        default='closing-soon',
        help='Sort order: closing-soon (urgency), new (fresh), hot-24h (momentum), volume (popularity) (default: closing-soon)'
    )
    parser.add_argument(
        '--category',
        type=str,
        help='Filter to specific category (e.g., Economics, Politics, Sports)'
    )
    parser.add_argument(
        '--status',
        choices=['open', 'closed', 'settled'],
        default='open',
        help='Event status filter (default: open)'
    )
    # Generate default timestamped filename
    default_filename = f"snapshot_{datetime.now().strftime('%Y_%m_%d_%H%M%S')}.md"
    
    parser.add_argument(
        '--output-file', '-o',
        default=default_filename,
        help=f'Output file path (default: {default_filename})'
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
        snapshot = client.analyze_snapshot(
            series,
            events,
            min_volume=args.min_volume,
            min_price=args.min_price,
            max_price=args.max_price,
            category_filter=args.category,
            sort_by=args.sort
        )

        # Generate output
        if args.output_format == 'json':
            output = json.dumps(snapshot, indent=2, default=str)
        elif args.output_format == 'csv':
            output = format_csv(snapshot)
        elif args.output_format == 'md':
            output = format_markdown(snapshot, args.top_n)
        else:  # console
            # Display to terminal with rich if available
            if RICH_AVAILABLE:
                display_with_rich(snapshot, args.top_n)
            else:
                display_plain(snapshot, args.top_n)
            return 0

        # Write output if file specified or if md/json/csv format chosen
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
