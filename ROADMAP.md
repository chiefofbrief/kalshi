# Kalshi Trading Roadmap & Strategy

Unified knowledge base for the Kalshi prediction market project.

---

## 1. Project Intelligence & Core Findings

### **A. Mutually Exclusive (ME) Arbitrage Truths**
*   **The "Exhaustivity" Trap (BUY Arb):** Many ME markets are **NOT exhaustive**. A "BUY Arb" (Sum < $1.00) is often a false signal; buying the set leads to 100% loss if "None of the Above" occurs. 
*   **The "Historical" Trap (Phantom Arb):** "Last Traded Price" is often stale. Scripts must use **YES Bids** for real-time arbitrage calculations.
*   **The Gold Standard (SELL Arb):** A guaranteed win occurs only when the **Sum of YES Bids > $1.00**.

### **B. Precision & Execution Truths**
*   **The $0.90+ Subpenny Rule:** In precision markets (tapered_deci_cent), outcomes priced >90¢ use **$0.001 (decicent) tick sizes**. Scripts must account for these to find entries like 92.5¢.
*   **The Settlement Haircut:** At resolution, payouts are **rounded down** to the nearest cent. For small positions, this fractional cent loss can significantly impact ROI.
*   **Maker vs. Taker:** In high-probability markets (80–96¢), do not "Pay the Ask" if the spread is wide. "Bid the Gap" (e.g., 95¢ on 94/96) to become a "Maker" and reduce fees.
*   **Annualized ROI Velocity:** A 2¢ profit in 4 hours is superior to a 2¢ profit in 4 weeks. Prioritize capital turnover speed.

### **C. Exit Framework**
*   **Settlement Exit**: Default for Certainty Gaps. Hold until finalized. (Note: Account for the settlement timer delay).
*   **Early Exit**: Reassess if price moves against you or a better "Velocity" opportunity appears elsewhere.

---

## 2. Active Toolset

| Tool | Status | Purpose |
| :--- | :---: | :--- |
| `platform_snapshot.py` | ✅ | **Discovery Engine**. Scans for liquidity and basic price gaps. |
| `event_drilldown.py` | ✅ | **Surgical Inspector**. Shows full order book, depth, and ME sums. |
| `certainty_gap_scanner.py`| ✅ | **ROI Specialist**. Ranks 80–96¢ markets by Annualized ROI. |
| `me_scanner.py` | ⚠️ | **Arb Hunter**. Needs update to prioritize YES Bids over Last Price. |

---

## 3. Development Roadmap (The "Hunter" Path)

### Level 1: Platform Crawler (Discovery)
*   **Goal:** Identify high-liquidity hubs in Economics, Politics, and Crypto.

### Level 2: ROI Specialist (Refinement)
*   **Goal:** Calculate true net profitability.
*   **Focus:** Accounting for **Subpenny Ticks**, **Series Fees**, and **Settlement Haircuts**.

### Level 3: Real-Time Sniper (Momentum)
*   **Goal:** Catch the "Consensus Spike" as it happens.
*   **Focus:** Building the **Tape Scanner** using WebSockets (`trade` channel).

### Level 4: Fundamental Validator (Sentiment)
*   **Goal:** Compare crowd forecast to market price.
*   **Focus:** Using **Forecast Percentile History** as an early warning for strike boundary breaches.

### Level 5: Alpha Hunter (Heat Maps)
*   **Goal:** Find "Invisible" interest in complex markets.
*   **Focus:** Using **MVE Lookup History** to identify which combos are being researched by traders.

---

## 4. Scripts to Build

### 1. The Tape Scanner (WebSockets)
**Purpose**: Real-time "Spike" detection.
- Monitors the `trade` channel for sudden bursts in volume.
- Signals when a price move (e.g., 70¢ → 92¢) is backed by broad consensus.

### 2. Drift Velocity Monitor
**Purpose**: Rank certainty gaps by their current momentum.
- Uses `Batch Get Market Candlesticks` to identify "heating up" markets.

### 3. Sentiment & Forecast Guard
**Purpose**: Early warning system for high-risk gaps.
- Uses `Forecast Percentile History`.
- Alerts if the crowd's median forecast is drifting dangerously close to your strike boundary.

### 4. MVE Heat Map
**Purpose**: Find emerging interest in complex combo markets.
- Uses `MVE Lookup History` to track which combos are getting research attention in the last 60 seconds.

---

## 6. Current Known Issues & Technical Debt

### **⚠️ Data Reliability (Critical)**
*   **Stale Metadata Trap**: The `expected_expiration_time` field in the API is often stale (in the past) while markets are still active. This caused "Ghost ROI" spikes (e.g., 186,000%). 
*   **Temporary Fix**: All ROI scripts have been reverted to use **`close_time`** (Hard Exchange Deadline) only. 
*   **Required Fix**: Implement a "Sanity Check" layer that compares `expected_expiration_time` against `now`. If expiration is in the past but market is `active`, use `close_time`.

### **⚠️ Discovery Efficiency**
*   **Hidden Sprints**: High-velocity trades are often buried in the API. Current "Dual-Path" scanning is a workaround but needs more rigor to ensure 100% coverage of preferred categories.

---

## 7. Immediate Next Steps & Research


- [ ] **Technical Update**: Update `certainty_gap_scanner.py` to use `Decimal` math and the `expected_expiration_time` for ROI.
- [ ] **Data Validation**: Compare `GET /live_data` against market prices for 3–5 active events to measure "Price Lag."
- [ ] **Backtest**: Use historical endpoints to measure the "Drift Success Rate" for 92¢ markets in Economics vs. Politics.
