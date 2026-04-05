#!/usr/bin/env python3
import requests
import sys
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from rich.console import Console
from rich.table import Table

# API Config
BASE_URL = "https://api.elections.kalshi.com/trade-api/v2/"
PREFERRED = ["Economics", "Politics", "Crypto", "Companies", "Financials", "Science and Technology", "Elections"]

def get_discovery_pool():
    """Path A: Broad Temporal Scan (60 days) + Path B: Category Deep-Dive."""
    max_close = int((datetime.now(timezone.utc) + timedelta(days=60)).timestamp())
    params = {'limit': 1000, 'status': 'open', 'max_close_ts': max_close}
    
    markets = []
    try:
        r = requests.get(f"{BASE_URL}markets", params=params)
        markets.extend(r.json().get('markets', []))
        
        for cat in ["Economics", "Politics", "Crypto"]:
            r = requests.get(f"{BASE_URL}events", params={'limit': 100, 'status': 'open', 'category': cat, 'with_nested_markets': 'true'})
            for e in r.json().get('events', []):
                for m in e.get('markets', []):
                    m['event_ticker_actual'] = e.get('ticker')
                    markets.append(m)
    except: pass
    return {m['ticker']: m for m in markets}.values()

def scan():
    console = Console()
    now = datetime.now(timezone.utc)
    
    with console.status("[bold blue]Performing Precision Discovery..."):
        pool = get_discovery_pool()
    
    found = []
    for m in pool:
        try:
            bid = Decimal(m.get('yes_bid_dollars', '0'))
            if Decimal('0.80') <= bid <= Decimal('0.96'):
                # Timing: HARD CLOSE TIME ONLY
                p_str = m.get('close_time')
                if not p_str: continue
                
                p_dt = datetime.fromisoformat(p_str.replace('Z', '+00:00'))
                delta = p_dt - now
                days = Decimal(max(delta.total_seconds() / 86400, 0.04))
                
                # ROI Math
                roi = ((Decimal('0.99') - bid) / bid) * 100
                ann_roi = roi * (Decimal('365') / days)
                
                s_ticker = m.get('series_ticker') or m.get('ticker', '').split('-')[0]
                
                found.append({
                    'title': m.get('title'),
                    'ticker': m.get('ticker'),
                    'e_ticker': m.get('event_ticker') or m.get('event_ticker_actual') or m.get('ticker').rsplit('-', 1)[0],
                    'bid': bid,
                    'ann': ann_roi,
                    'days': float(days),
                    'cat': m.get('category', 'Misc'),
                    'url': f"https://kalshi.com/markets/{s_ticker.lower()}"
                })
        except: continue

    found.sort(key=lambda x: x['ann'], reverse=True)

    table = Table(title="💎 Certainty Gap Discovery (Hard Close Only)")
    table.add_column("Market", width=45)
    table.add_column("Price")
    table.add_column("Ann. ROI", justify="right", style="bold green")
    table.add_column("Close In", justify="right", style="cyan")
    
    for o in found[:25]:
        table.add_row(o['title'][:42]+"...", f"${o['bid']}", f"{o['ann']:,.0f}%", f"{o['days']:.1f}d")
    
    console.print(table)
    
    with open("master_gap_report.md", "w") as f:
        f.write("# Master Certainty Gap Report (Hard Close Only)\n\n")
        f.write("| Market | Price | ROI (Ann) | Close In | URL | Drilldown |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for o in found[:100]:
            f.write(f"| {o['title']} | ${o['bid']} | {o['ann']:,.0f}% | {o['days']:.1f}d | [Trade]({o['url']}) | `python event_drilldown.py {o['e_ticker']}` |\n")
    
    console.print(f"\n[bold green]✅ Master report saved to master_gap_report.md[/bold green]")

if __name__ == "__main__":
    scan()
