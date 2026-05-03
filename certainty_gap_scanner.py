#!/usr/bin/env python3
import requests
import sys
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from rich.console import Console
from rich.table import Table

# API Config
BASE_URL = "https://api.elections.kalshi.com/trade-api/v2/"

# STRICT CATEGORY LIMIT (Mirrors Platform Snapshot)
CORE_CATEGORIES = [
    "Economics", "Financials", "Companies", "Politics", 
    "Elections", "Science and Technology", "Crypto"
]

def get_discovery_pool():
    """Fetches markets ONLY from the Core Categories, paginating each fully."""
    markets = []
    for cat in CORE_CATEGORIES:
        cursor = None
        while True:
            try:
                params = {
                    'limit': 200,
                    'status': 'open',
                    'category': cat,
                    'with_nested_markets': 'true'
                }
                if cursor:
                    params['cursor'] = cursor
                r = requests.get(f"{BASE_URL}events", params=params)
                data = r.json()
                for e in data.get('events', []):
                    for m in e.get('markets', []):
                        m['event_ticker_actual'] = e.get('ticker')
                        m['category_actual'] = cat
                        markets.append(m)
                cursor = data.get('cursor')
                if not cursor:
                    break
            except:
                break
    
    # Deduplicate by ticker (just in case)
    return {m['ticker']: m for m in markets}.values()

def scan():
    console = Console()
    now = datetime.now(timezone.utc)
    
    with console.status(f"[bold blue]Scouting Certainty Gaps in {len(CORE_CATEGORIES)} Core Categories..."):
        pool = get_discovery_pool()
    
    found = []
    for m in pool:
        try:
            bid = Decimal(m.get('yes_bid_dollars', '0'))
            # Certainty Gap Range: 80-96c
            if Decimal('0.80') <= bid <= Decimal('0.96'):
                # Timing: HARD CLOSE TIME (Source of Truth)
                p_str = m.get('close_time')
                if not p_str: continue
                
                p_dt = datetime.fromisoformat(p_str.replace('Z', '+00:00'))
                delta = p_dt - now
                days = Decimal(max(delta.total_seconds() / 86400, 0.04))
                
                # ROI Math
                roi = ((Decimal('0.99') - bid) / bid) * 100
                ann_roi = roi * (Decimal('365') / days)
                
                # UI Link
                s_ticker = m.get('series_ticker') or m.get('ticker', '').split('-')[0]
                ui_link = f"https://kalshi.com/markets/{s_ticker.lower()}"
                
                found.append({
                    'title': m.get('title'),
                    'ticker': m.get('ticker'),
                    'e_ticker': m.get('event_ticker') or m.get('event_ticker_actual') or m.get('ticker').rsplit('-', 1)[0],
                    'bid': bid,
                    'ann': ann_roi,
                    'days': float(days),
                    'cat': m.get('category_actual', 'Misc'),
                    'url': ui_link
                })
        except: continue

    # Sort by Annualized ROI
    found.sort(key=lambda x: x['ann'], reverse=True)

    # Show Top 25
    table = Table(title=f"💎 Certainty Gaps: {', '.join(CORE_CATEGORIES[:3])}...")
    table.add_column("Market", width=45)
    table.add_column("Price")
    table.add_column("Ann. ROI", justify="right", style="bold green")
    table.add_column("Close In", justify="right", style="cyan")
    table.add_column("Category", style="dim")
    
    for o in found[:25]:
        table.add_row(o['title'][:42]+"...", f"${o['bid']}", f"{o['ann']:,.0f}%", f"{o['days']:.1f}d", o['cat'])
    
    console.print(table)
    
    # Save Report
    report_name = "core_gap_report.md"
    with open(report_name, "w") as f:
        f.write(f"# Core Certainty Gap Report\nLimited to: {', '.join(CORE_CATEGORIES)}\n\n")
        f.write("| Market | Category | Price | ROI (Ann) | Close In | Drilldown |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for o in found[:100]:
            f.write(f"| [{o['title']}]({o['url']}) | {o['cat']} | ${o['bid']} | {o['ann']:,.0f}% | {o['days']:.1f}d | `python event_drilldown.py {o['e_ticker']}` |\n")
    
    console.print(f"\n[bold green]✅ Limited report saved to {report_name}[/bold green]")

if __name__ == "__main__":
    scan()
