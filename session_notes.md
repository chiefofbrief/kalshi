# Kalshi Session Notes - March 4, 2026

## 1. Strategic Findings: The "Calculated" Logic

### **A. Mutually Exclusive (ME) Arbitrage Truths**
During this session, we stress-tested the arbitrage scanner and discovered two critical "traps" that we have now mathematically solved in the script:

*   **The "Exhaustivity" Trap (BUY Arb):** We found that many Kalshi markets (like "Next US Recession" or "51st State") are mutually exclusive (only one can win) but **NOT exhaustive** (none of them might happen). 
    *   *Finding:* A "BUY Arb" signal (Sum < $1.00) is often a false signal. If you buy the set and "None of the Above" happens, you lose 100% of your capital.
    *   *Decision:* We have **disabled BUY Arb signals** in the summary to protect against this risk.
*   **The "Historical" Trap (Phantom Arb):** Many arbs appear real because the **Last Traded Price** is high (e.g., a $1.88 sum for CPI). 
    *   *Finding:* These are "ghost" prices from weeks ago. If the current **YES Bids** are 0¢, you cannot actually sell your set for a profit.
    *   *Decision:* The script now ignores "Last Price" for signals and calculates the **Sum of YES Bids**.
*   **The Gold Standard (SELL Arb):** A "SELL Arb" occurs when the **Sum of YES Bids > $1.00**. 
    *   *Calculated Logic:* This is a guaranteed win. If you sell the set (buy NO on all outcomes) for a total Bid sum of $1.04, you are guaranteed to collect $1.00 (if one hits) or $1.04 (if none hit). This is the only arb signal the summary now flags.

### **B. Certainty Gap Execution**
*   **Maker vs. Taker:** We analyzed the "Top AI Model" market.
    *   *The Spread:* 94¢ Bid / 96¢ Ask.
    *   *Calculated Play:* Do not "Pay the Ask" (96¢). Instead, "Bid the Gap" at **95¢** using a **Limit Order**. 
    *   *Result:* This makes you a "Maker" (often $0 fees) and increases your ROI from 4.1% to 5.2% in 48 hours.

---

## 2. Toolset State & Usage

### **platform_snapshot.py**
This is your daily discovery engine. It has been transformed into a surgical reporting tool.
*   **Core Filter:** Automatically targets the **Big Seven** categories: Economics, Financials, Companies, Politics, Elections, Science & Tech, Crypto.
*   **Output:** Generates a timestamped `.md` file with a vertical card layout and clickable links.
*   **Usage:**
    ```bash
    python platform_snapshot.py
    ```
*   **New Logic:**
    *   **Hyperlinks:** Uses series-prefix URLs (e.g., `/markets/kxbtc`) for maximum reliability.
    *   **Age:** Uses the `open_time` API field to show how long a market has been listed (e.g., "2mo").
    *   **Zombies:** Automatically excludes any event where all internal markets are closed.

### **event_drilldown.py**
Used for surgical inspection of a specific trade before execution.
*   **Usage:**
    ```bash
    python event_drilldown.py <EVENT_TICKER>
    ```
*   **Function:** Reveals the full order book (Bids/Asks) and liquidity (Volume/OI) for every strike in an event.

---

## 3. Pending Items

- [ ] **Summary Priority:** Update the "Certainty Gap" summary section to sort matches by **Closing Date** (soonest first). This ensures the most urgent trades are always at the top of the file.
- [ ] **Execution:** Place the 95¢ Limit Order for `KXTOPMODEL-26MAR07-CLAUDE46` once funding is resolved.
- [ ] **Arb Threshold:** Monitor if the SELL Arb filter (`sum_bid > 100`) is too strict; consider a "Near-Arb" warning for sums > 98¢.
