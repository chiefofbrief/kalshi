# Kalshi API Strategy & Development Roadmap

## I. Core Component Map
These are the foundational endpoints required to move from discovery to execution.

| Category | Endpoint | Primary Use | Auth Required? |
| :--- | :--- | :--- | :--- |
| **Discovery** | `GET /series` | Find a category (e.g., Economics, Weather). | No |
| **Discovery** | `GET /events` | Find specific dates/instances of a category. | No |
| **Discovery** | `GET /markets` | Get tradable contracts (Yes/No prices). | No |
| **Analysis** | `GET /markets/trades` | See actual transaction history for a market. | No |
| **Analysis** | `GET /candlesticks` | View OHLC price charts over time. | No |
| **Analysis** | `GET /orderbook` | See depth (how many bids at what price). | No |
| **Alpha** | `GET /live_data` | See the real-world "source of truth" data. | **Yes** |
| **Portfolio** | `GET /balance` | Check your available cash in cents. | **Yes** |
| **Portfolio** | `GET /positions` | See what you currently own. | **Yes** |
| **Portfolio** | `GET /fills` | See your actual completed transactions. | **Yes** |
| **Execution** | `POST /orders` | Place a new trade. | **Yes** |

---

## II. Logical Development Progression
Build these scripts in order to gradually increase your technical and market familiarity.

### Level 1: The Platform Crawler
* **Goal:** "What exists on this platform and what is actually being traded?"
* **Endpoints:** `GET /series`, `GET /events`
* **Workflow:** Fetch all series to get a list of active topics. Fetch all open events. Sort events by **Volume** to find the "active" hubs.
* **Why:** Focuses your attention where there is enough liquidity to actually trade.

### Level 1.5: The Event Drill-Down
* **Goal:** "I found a category I like. What are the specific bets available?"
* **Endpoints:** `GET /events/{ticker}` with `with_nested_markets=true`
* **Workflow:** Input an `event_ticker` (e.g., `FED-26JAN26`). Extract every market inside it.
* **Why:** This is the bridge between a topic and a trade. It shows you the full "distribution" of what people expect to happen.

### Level 2: The Logic Auditor (Pricing Mislocations)
* **Goal:** "Is the crowd's math logically broken?"
* **Endpoints:** `GET /markets`
* **Workflow:** Find an event with mutually exclusive outcomes (e.g., Fed cannot hike 25bps AND 50bps). Sum the `yes_price` of every outcome.
* **The "Edge":** If the total sum is 90¢, the market is "missing" 10¢ of probability. Buying the whole set theoretically guarantees a 10¢ profit (excluding fees).
* **Why:** This is the most basic "Arb" (Arbitrage). It is pure math with no outside news required.

### Level 3: The Spread Sniper (Efficiency Analysis)
* **Goal:** "Where can I trade without losing my edge to the middleman?"
* **Endpoints:** `GET /orderbook`
* **Workflow:** Calculate the real **YES Ask** ($100 - \text{NO Bid}$). Compare it to the **YES Bid**. 
* **Why:** A "mispriced" market at 50¢ is useless if the spread is 10¢. You are hunting for 1–2¢ spreads.

### Level 4: The Milestone Watcher (Information Edge)
* **Goal:** "Does the data move faster than the price?"
* **Endpoints:** `GET /live_data` (Auth required), `GET /markets/trades`
* **Workflow:** Monitor real-time "Milestones" (e.g., live rainfall data). Compare it to the market's price for that outcome.
* **Why:** This is where speed beats the crowd. If the data updates but the price hasn't moved yet, you have a sniping opportunity.

### Level 5: The "Dry Powder" Manager (Account Operations)
* **Goal:** "What can I actually afford to trade right now?"
* **Endpoints:** `GET /portfolio/balance`, `GET /portfolio/positions`
* **Workflow:** Pull balance and current positions. Calculate your "Unrealized P&L" and weighted exposure (e.g., "Am I too heavy in Weather?").
* **Why:** Prevents you from being over-leveraged before placing an automated trade.

---

## III. Pro-Tips for Implementation
* **Signatures:** For Level 4 and 5, remember that you must sign the **Path without Query Parameters** (e.g., sign `/trade-api/v2/portfolio/orders`, not `/trade-api/v2/portfolio/orders?limit=5`).
* **Timing:** `KALSHI-ACCESS-TIMESTAMP` must be in **milliseconds**.
* **JSON Handling:** Always use `with_nested_markets=true` for Event discovery; it saves you dozens of individual API calls to individual Market tickers.
