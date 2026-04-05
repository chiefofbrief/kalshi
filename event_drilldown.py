#!/usr/bin/env python3
"""
Kalshi Event Drill-Down Tool v1.2 - Hard Close Alignment

PURPOSE:
    Deep analysis of individual events. Strictly aligned with HARD CLOSE TIME.
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

# API Configuration
BASE_URL = "https://api.elections.kalshi.com/trade-api/v2/"

class KalshiEventDrilldown:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = urljoin(self.base_url, endpoint)
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_event(self, event_ticker: str) -> Dict[str, Any]:
        params = {'with_nested_markets': 'true'}
        data = self._get(f'events/{event_ticker}', params=params)
        return data.get('event', {})

    def analyze_event(self, event: Dict[str, Any], sort_by: str = 'price') -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        markets = event.get('markets', [])
        enriched_markets = []
        for market in markets:
            enriched = dict(market)
            bid_str = market.get('yes_bid_dollars', '0')
            ask_str = market.get('yes_ask_dollars', '0')
            
            try:
                enriched['yes_price_cents'] = int(float(bid_str) * 100)
                enriched['yes_bid_cents'] = int(float(bid_str) * 100)
                enriched['yes_ask_cents'] = int(float(ask_str) * 100)
                enriched['no_price_cents'] = 100 - enriched['yes_price_cents']
                enriched['spread_cents'] = enriched['yes_ask_cents'] - enriched['yes_bid_cents'] if enriched['yes_bid_cents'] > 0 else None
            except: enriched['yes_price_cents'] = 0

            enriched['volume'] = int(float(market.get('volume_fp', 0)))
            enriched['open_interest'] = int(float(market.get('open_interest_fp', 0)))

            # Timing: HARD CLOSE ONLY
            c_time_str = market.get('close_time')
            if c_time_str:
                enriched['close_dt'] = datetime.fromisoformat(c_time_str.replace('Z', '+00:00'))
            else: enriched['close_dt'] = None

            enriched['outcome'] = market.get('yes_sub_title') or market.get('title', '')
            enriched_markets.append(enriched)

        # Sort
        enriched_markets.sort(key=lambda m: -m['yes_price_cents'])
        
        close_dates = [m['close_dt'] for m in enriched_markets if m['close_dt']]
        earliest_close = min(close_dates) if close_dates else None

        return {
            'event': event,
            'markets': enriched_markets,
            'summary': {
                'total_volume': sum(m['volume'] for m in enriched_markets),
                'earliest_close': earliest_close.isoformat() if earliest_close else None,
                'sum_yes_prices_cents': sum(m['yes_price_cents'] for m in enriched_markets)
            }
        }

def format_time(dt_str: Optional[str]) -> str:
    if not dt_str: return "Unknown"
    dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    delta = dt - datetime.now(timezone.utc)
    if delta.days < 0: return "Closed"
    return f"{delta.days}d {delta.seconds // 3600}h"

def display(analysis: Dict[str, Any]):
    console = Console()
    e = analysis['event']
    s = analysis['summary']
    
    console.print(Panel(f"[bold white]{e['title']}[/bold white]\n[dim]Ticker: {e['ticker']} | ME: {e.get('mutually_exclusive')}[/dim]", border_style="cyan"))
    
    stats = Table(box=box.SIMPLE, show_header=False, expand=True)
    stats.add_row("Total Vol", str(s['total_volume']), "Close In", format_time(s['earliest_close']), "Prob Sum", f"${s['sum_yes_prices_cents']/100:.2f}")
    console.print(stats)

    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Outcome", width=30)
    table.add_column("Price", justify="right")
    table.add_column("Bid/Ask", justify="center")
    table.add_column("Vol", justify="right")
    
    for m in analysis['markets']:
        table.add_row(m['outcome'][:30], f"{m['yes_price_cents']}¢", f"{m['yes_bid_cents']}/{m['yes_ask_cents']}", str(m['volume']))
    console.print(table)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('ticker')
    args = parser.parse_args()
    client = KalshiEventDrilldown()
    display(client.analyze_event(client.get_event(args.ticker)))

if __name__ == '__main__':
    main()
