# Kalshi Trading Development Roadmap

## Context & Learnings

### Platform Understanding
- **8,104 series** across the platform with varying frequencies (hourly, daily, weekly, custom)
- **~4,000 open events** at any given time, but only **~470** with meaningful volume (≥50k) and profit room (≤97¢)
- **Total volume**: 780M+ contracts traded
- **Top categories by volume**: Sports (393M), Politics (216M), Economics (39M), Crypto (28M)
- **Data freshness**: Markets have both total volume (historical) and 24h volume (current activity)
- **Price efficiency**: Most markets 98-99¢ have no profit room after fees

### User Preferences & Workflow
- **Domain focus**: Economics, Financials, Companies (for research-backed trading)
- **Preferred approach**: Start simple, add complexity incrementally based on actual patterns in data
- **Value of tools**: Scripts should surface actionable opportunities, not just dump data
- **Time horizons**: Weekly/daily discovery workflow (not high-frequency)
- **Decision making**: Prefer seeing temporal urgency (closing soon) over historical popularity

### API Capabilities (Public, No Auth Required)
- `GET /series` - Series metadata with volume aggregates
- `GET /events` - Events with pagination (200/page), supports `with_nested_markets=true`
- `GET /events/{ticker}` - Detailed event data (for drill-down)
- `GET /market/{ticker}/orderbook` - Order book depth (requires auth)
- `GET /market/{ticker}/candlesticks` - Historical price/volume data
- Market data includes: volume, volume_24h, open_interest, bid/ask prices, close times

---

## Scripts to Build

### 1. Event Drill-Down Tool ✅ COMPLETE
**Purpose**: Bridge gap between discovery (platform_snapshot.py) and execution

**Script**: `event_drilldown.py`

**What it does**:
- Takes event ticker as input (e.g., `FED-26JAN24`)
- Displays ALL markets within that event in a compact, readable table
- Shows each market's outcome, YES price, bid/ask, spread, volume, open interest
- Identifies if event is mutually exclusive and calculates sum of YES prices
- **Built-in arbitrage analysis**: Flags when sum ≠ $1.00 for mutually exclusive events
- Supports sorting by: price (default), volume, strike, spread
- Export formats: console (rich), JSON, CSV

**Usage**:
```bash
python event_drilldown.py FED-26JAN29              # Basic drill-down
python event_drilldown.py KXNEWPOPE-70 --sort volume  # Sort by liquidity
python event_drilldown.py CPI-26FEB14 -o data.json --output-format json
```

**Key endpoints**: `GET /events/{ticker}` with `with_nested_markets=true`

---

### 2. Mutually Exclusive Validator (Sum-of-Probabilities Check)
**Purpose**: Find mechanical arbitrage opportunities (Strategy 5 from notes)

**Status**: Partially complete - arb analysis built into `event_drilldown.py`

**What it does**:
- Scans events where `mutually_exclusive=true`
- Sums YES prices across all markets in the event
- Flags events where sum ≠ $1.00 (e.g., sum = 95¢)
- Calculates potential profit after fees

**Current capability**: Event Drill-Down already shows sum of YES prices and flags arbitrage opportunities for individual events. Missing: batch scanning across all mutually exclusive events.

**Value**:
- Risk-free (minus fees) arbitrage opportunities
- Mechanical strategy requiring no domain knowledge
- Teaches market structure and edge identification

**Key endpoints**: `GET /events`, parse `mutually_exclusive` field, sum market prices

**Note**: Opportunities likely rare and fleeting (bot territory), but educational to find manually

---

### 3. Spread/Efficiency Analyzer
**Purpose**: Identify where you can trade without losing to bid-ask spread

**What it does**:
- For a list of interesting events (from snapshot), pull order book data
- Calculate bid-ask spread for each market
- Flag markets with narrow spreads (<2¢) vs wide spreads (>5¢)
- Show liquidity at best bid/ask

**Value**:
- A market priced at 50¢ might have 48¢ bid / 52¢ ask (4¢ spread = profit eroded)
- Find efficient markets where your edge isn't eaten by friction
- Critical for Strategies 1, 2, 3 (any manual trading)

**Key endpoints**: `GET /market/{ticker}/orderbook` (requires authentication)

**Blocker**: This requires auth, unlike our current scripts. May need to implement later.

---

### 4. Price History Tracker (Certainty Gap Monitor)
**Purpose**: Track how markets in 90-97¢ range evolve toward 99¢

**What it does**:
- Takes a list of events (from snapshot filtered to --min-price 90)
- Fetches historical candlestick data over time
- Shows which markets successfully drifted from 92¢ → 99¢
- Calculates typical time horizon and volatility

**Value**:
- Validate Strategy 1 (Certainty Gap) with historical data
- Understand which categories/market types exhibit the pattern
- Build confidence before capital deployment

**Key endpoints**: `GET /market/{ticker}/candlesticks`

**Parameters**: Need to specify `start_ts`, `end_ts`, `period_interval` (1min, 1hr, 1day)

---

### 5. Category Performance Dashboard
**Purpose**: Understand which categories/series are worth focusing on

**What it does**:
- Aggregate volume, average spreads, market count by category
- Show trends over time (if we collect snapshots daily/weekly)
- Identify "hot" categories vs stagnant ones
- Could be static analysis or time-series if we snapshot regularly

**Value**:
- Data-driven category selection (vs guessing)
- Spot emerging opportunities (e.g., Crypto heating up)
- Focus research time on categories with action

**Key endpoints**: Aggregate data from `GET /series`, `GET /events`

**Note**: May just be enhanced version of platform_snapshot.py with historical comparison

---

### 6. New Market Alerter (Fresh Opportunity Detector)
**Purpose**: Get notified when markets matching your criteria appear

**What it does**:
- Save your filter preferences (category, min_volume, price_range)
- Run platform_snapshot.py on schedule (cron/scheduled task)
- Compare to previous snapshot, identify NEW markets
- Alert on new matches (email, terminal output, CSV diff)

**Value**:
- Automate the "check for new opportunities" workflow
- Get in early before prices reflect consensus (Strategy 2)
- No need to manually run discovery daily

**Key endpoints**: Same as platform_snapshot.py, plus local state storage

**Implementation**: Could be simple bash script wrapping platform_snapshot.py

---

## Strategies to Pursue (TIER 1 - Manual Testable)

### Strategy 1: Certainty Gap (90-97¢)
**Thesis**: Markets priced 90-97¢ drift toward 99¢ as settlement approaches, capturing 2-7¢ profit

**Tools needed**:
- platform_snapshot.py (filtering with `--min-price 90`)
- Event Drill-Down (verify outcome is genuinely certain)
- Spread Analyzer (ensure tight spreads)

**Validation**: Price History Tracker to see historical success rate

**Risk**: Capital locked until settlement, outcome not as certain as believed

---

### Strategy 2: Fresh Opportunities (Information Speed)
**Thesis**: Newly created markets haven't reached consensus pricing yet

**Tools needed**:
- platform_snapshot.py (sorting with `--sort new`)
- Event Drill-Down (understand the new market)
- Domain research (use your expertise to assess true probability)

**Validation**: Compare early prices to prices 24-48 hours later

**Risk**: Market may be new because it's low-interest (no liquidity)

---

### Strategy 3: Closing Urgency (Fast Turnover)
**Thesis**: Focus on markets closing soon for faster capital recycling

**Tools needed**:
- platform_snapshot.py (default `--sort closing-soon`)
- Event Drill-Down (quick decision making)

**Validation**: Track win rate and capital velocity ($/day vs $/month)

**Risk**: Rushed decisions, less time to research

---

### Strategy 4: Domain Expertise (Economics/Financials)
**Thesis**: Your research background gives you edge in specific categories

**Tools needed**:
- platform_snapshot.py (filtering with `--category Economics`)
- Event Drill-Down (detailed market analysis)
- External research (Fed statements, economic data, etc.)

**Validation**: Track performance by category to confirm edge exists

**Risk**: Overconfidence in domain knowledge, market may know something you don't

---

### Strategy 5: Range Bets (Low Volatility Play)
**Thesis**: Profit when outcome falls within specific range (e.g., CPI 3.0-3.5%)

**Tools needed**:
- Event Drill-Down (identify two-leg structure)
- Manual execution (buy YES on lower bound, buy NO on upper bound)

**Validation**: Historical volatility analysis for the indicator

**Risk**: Requires two trades (double fees), limited profit potential

---

## Deferred Strategies (TIER 2-3 - Require Automation or Auth)

### Tier 2: Manual + Simple Automation
- **Statistical Modeling**: Build forecast models for predictable markets (temperature, search volume)
- **Correlated Pairs**: Find markets that should move together but are priced independently

**Blocker**: Need historical data collection and statistical tools

### Tier 3: Requires API Authentication
- **Sum-of-Probabilities Arbitrage**: Automated scanning for mutually exclusive events
- **Spread Sniper**: Real-time order book monitoring
- **Market Making**: Provide liquidity for spread + incentives

**Blocker**: Need to implement authentication, order placement, real-time data handling

---

## Immediate Next Steps

1. ✅ **Test platform_snapshot.py with Age column** - Complete
2. ✅ **Build Event Drill-Down script** - Complete (`event_drilldown.py`)
3. **Manually test Strategy 1 (Certainty Gap)** - Run snapshot with `--min-price 90`, pick 3-5 markets, paper trade for 1-2 weeks
4. **Manually test Strategy 4 (Domain Expertise)** - Run snapshot with `--category Economics`, research 2-3 events, track decisions
5. **Document learnings** - What worked, what didn't, refine filters/thresholds

**Decision point after manual testing**: Do the strategies show promise? If yes, build automation. If no, refine hypotheses.

---

## Questions to Answer Through Testing

1. **Certainty Gap**: Do 90-97¢ markets reliably drift to 99¢? What's the typical time horizon?
2. **Volume thresholds**: Is 50k the right cutoff, or should we go higher/lower?
3. **Category focus**: Which categories show the best combination of volume + opportunity?
4. **Spread impact**: How much does bid-ask spread erode theoretical edge?
5. **Time horizon**: Weekly discovery + holding or daily monitoring + quick flips?

These answers will inform which scripts to prioritize and which strategies to automate.
