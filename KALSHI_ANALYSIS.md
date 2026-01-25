# Kalshi Analysis Reference

Quick reference for interpreting script outputs and applying trading strategies.

---

## 1. Column Definitions

### platform_snapshot.py Output

| Column | Definition |
|--------|------------|
| Event | Title of the prediction market event |
| Event Ticker | Unique identifier for the event (use with `event_drilldown.py`) |
| Category | Market category (Economics, Politics, Sports, etc.) |
| Age | Time since event was created (e.g., "2d" = 2 days old) |
| Close | Time until earliest market in event closes (e.g., "6d" = closes in 6 days) |
| Volume | Total contracts ever traded across all markets in this event |
| Vol 24h | Contracts traded in the last 24 hours |
| Open Int | Current open positions (contracts held, not yet settled) |
| Price Range | Min-Max YES prices across all markets in the event (in dollars) |
| Mkts | Number of individual markets within this event |

### event_drilldown.py Output

| Column | Definition |
|--------|------------|
| Outcome | The specific outcome being traded (e.g., "Before 2027", "Yes", "450-474 bps") |
| YES | Last traded price for YES contracts (in cents) |
| Bid/Ask | Best available bid and ask prices (in cents) |
| Sprd | Spread between bid and ask (in cents) |
| Volume | Total contracts traded for this specific market |
| 24h | Contracts traded in last 24 hours for this market |
| OI | Open interest for this specific market |

**Sum of YES Prices**: For mutually exclusive events, shows total of all YES prices. Mathematically should equal $1.00 if market is perfectly efficient.

### me_scanner.py Output

| Column | Definition |
|--------|------------|
| Top Mkt | The market with highest price within your filter range |
| Price | Price of that top market (in cents) |
| Sum | Sum of all YES prices across all markets in the event |
| Arb | Deviation from $1.00 in cents (negative = sum < $1, positive = sum > $1) |

---

## 2. Strategies (Actionable with Current Tools)

### Strategy 1: Certainty Gap

**Thesis**: Markets priced 80-97 cents represent high-confidence outcomes that may drift toward 99 cents as settlement approaches.

**Tools**:
```bash
# Find certainty gap candidates
python platform_snapshot.py --min-price 80 --max-price 97

# Or scan ME events specifically
python me_scanner.py --min-price 80 --max-price 97

# Drill down to verify
python event_drilldown.py <EVENT_TICKER>
```

**What to verify in drilldown**:
- Is the outcome genuinely likely based on your assessment?
- What is the settlement source/rule?
- When does the market close?

**Capital consideration**: Capital is locked until settlement.

---

### Strategy 2: Fresh Opportunities

**Thesis**: Newly created markets haven't reached consensus pricing yet. Early information may provide edge.

**Tools**:
```bash
# Sort by newest markets
python platform_snapshot.py --sort new

# Drill down into interesting new markets
python event_drilldown.py <EVENT_TICKER>
```

**What to check**:
- Why was this market created now?
- Do you have relevant information others might not have priced in?
- Is there sufficient volume to enter/exit?

---

### Strategy 3: Domain Expertise

**Thesis**: Focus on categories where your research background provides informational edge.

**Tools**:
```bash
# Filter to your domain
python platform_snapshot.py --category Economics
python platform_snapshot.py --category Financials

# Deep dive
python event_drilldown.py <EVENT_TICKER>
```

**What to leverage**:
- Your understanding of how indicators are calculated
- Access to primary sources (Fed statements, economic data releases)
- Familiarity with historical patterns

---

### Strategy 4: Sum-of-Probabilities (ME Events)

**Thesis**: In mutually exclusive events, sum of YES prices should equal $1.00. Deviations represent potential arbitrage.

**Tools**:
```bash
# Find ME events with biggest deviations
python me_scanner.py --sort arb

# Check specific event
python event_drilldown.py <EVENT_TICKER>
```

**Interpretation**:
- Sum < $1.00: Buying all outcomes costs less than guaranteed $1.00 payout
- Sum > $1.00: Selling all outcomes yields more than the $1.00 you'd owe

**Consideration**: Fees, execution costs, and capital lockup affect actual profitability.

---

### Strategy 5: Closing Urgency

**Thesis**: Markets closing soon require decisions now. Faster capital turnover if correct.

**Tools**:
```bash
# Default sort is closing-soon
python platform_snapshot.py

# Or explicit
python platform_snapshot.py --sort closing-soon
```

**Trade-off**: Less time to research vs. faster resolution.

---

## 3. Exit Framework

### Settlement Exit
- Hold until market settles
- No action required
- Capital locked until resolution

### Early Exit Considerations
- Price moved in your favor: lock in gains vs. wait for full settlement
- Price moved against you: cut losses vs. thesis still valid
- New information emerged: reassess original thesis
- Better opportunity elsewhere: opportunity cost of locked capital

### What to Monitor While Holding
- News/events relevant to the outcome
- Price movement (is thesis playing out?)
- Volume changes (others entering/exiting?)
- Time to settlement

---

## 4. Workflow

```
1. Discovery
   python platform_snapshot.py [filters]

2. Scan (if looking for ME opportunities)
   python me_scanner.py [filters]

3. Drill Down
   python event_drilldown.py <TICKER>

4. Research
   - Settlement rules
   - Primary sources
   - Your thesis

5. Decision
   - Enter / Skip / Watchlist
```
