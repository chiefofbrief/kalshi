# Kalshi API V2 Reference (Ground Truth)

## 1. Exchange Hierarchy & Terminology

### Market
*   **Definition**: A single binary outcome (e.g., "YES" or "NO" for a specific condition).
*   **Granularity**: The lowest-level object in the API. Individual tickers (like `KXBONDIOUT-APR09`) refer to specific markets.

### Event
*   **Definition**: A collection of related markets grouped around a single real-world topic or date.
*   **Granularity**: The primary unit of interaction for members. 

### Series
*   **Definition**: A collection of recurring events sharing the same prefix and rule template.
*   **Rules**:
    *   Events within a series use similar data for determination but cover disjoint time periods (e.g., "Monthly Jobs Report").
    *   There is no logical outcome dependency between events in a series.
    *   All events in a series share the same ticker prefix (e.g., `KXFED`).

## 2. Public Access & Data Conventions

### Authorized Public Endpoint
*   **Base URL**: `https://api.elections.kalshi.com/trade-api/v2`
*   **Scope**: Despite the subdomain, this is the authoritative production endpoint for **all** unauthenticated public market data (Economics, Tech, etc.). No API keys are required for "Discovery" or "Analysis" endpoints.

### UI Linking Convention
*   **Format**: `https://kalshi.com/markets/{series_ticker_lowercase}`
*   **Utility**: "Hunter" scripts should use this pattern to generate direct links to the Kalshi web interface for manual trade execution.

### Pagination Standard (Cursor-Based)
*   **Parameters**: `limit` (max items per page) and `cursor` (pointer to next page).
*   **Termination**: Stop when the `cursor` field is null or missing.
*   **Consistency Warning**: Data can change between page requests. High-velocity scanners should be aware that the first page of results may be stale by the completion of a full platform crawl.
*   **Supported Endpoints**: `/markets`, `/events`, `/series`, `/markets/trades`, `/portfolio/history`, `/portfolio/fills`, `/portfolio/orders`.

### Orderbook Structure (Fixed-Point)
*   **Primary Path**: `orderbook_fp`
*   **Bid Lists**: `yes_dollars` and `no_dollars`.
*   **Data Format**: Each entry is a string array: `[price_dollars, count_fp]`.
*   **Sorting**: Arrays are sorted by price **ascending**.
*   **Best Bid**: The highest bid (best price) is the **last element** in the array.
*   **Reciprocity Rule**: The API only returns Bids.
    *   `YES Ask = $1.00 - Best NO Bid`
    *   `NO Ask = $1.00 - Best YES Bid`
*   **Precision Recommendation**: Use the `Decimal` library for all price arithmetic to maintain sub-penny accuracy and avoid floating-point errors.
*   **Scaling Tip**: For contract counts (`_fp`), internally multiply by 100 and cast to an integer (e.g., "1.55" contracts = 155 units) to maintain precision using integer math.

## 2. Market Constraints & Validation Rules

### Price Boundaries & Tick Sizes
*   **Valid Range**: Prices must be between **$0.01 and $0.99**.
*   **Tick Size (Standard)**: Most markets use `linear_cent` ($0.01 intervals).
*   **Tick Size (Precision)**: Markets using `tapered_deci_cent` or `deci_cent` support **$0.001 (decicent)** precision.
    *   **The $0.90+ Rule**: In `tapered_deci_cent` markets, outcomes priced **above $0.90** (and below $0.10) use $0.001 tick sizes. Certainty Gap scripts must account for these sub-penny prices to accurately calculate ROI and identify entry points.

### Order Deduplication (Execution Standard)
*   **Field**: `client_order_id`
*   **Standard**: UUID4 string.
*   **Execution Behavior (For Future Automation)**: 
    *   **Success**: Returns `201 Created`.
    *   **Deduplication**: Returns `409 Conflict` if the `client_order_id` has already been used, preventing accidental double-ordering.
    *   **Validation**: Returns `400 Bad Request` for prices outside the 1–99¢ range.

## 3. Market Structure & Discovery (Scouting)

### Get Series
*   **Endpoint**: `GET /series/{series_ticker}`
*   **Utility**: **The Source of Truth (Rules & Settlement).** Returns the full metadata for a recurring market template.
    *   **Rule Verification**: Essential for "Hunter" scripts to confirm the exact settlement criteria (e.g., "Which official indicator is used?") and sources (e.g., "The BLS website") before a trade is recommended.
    *   **Historical Volume Analysis**: The `include_volume=true` parameter allows for measuring the long-term liquidity and popularity of a category over thousands of past events.
    *   **Contextual Data**: Provides the title, description, and frequency (daily, weekly, etc.) that give the Certainty Gap price point its real-world meaning.

### Get Series List
*   **Endpoint**: `GET /series`
*   **Utility**: **Category Scouting & Discovery.** The starting point for identifying new market themes.
    *   **Domain Focus**: The `category` and `tags` parameters allow scouting tools to isolate specific high-value categories (e.g., Economics, Financials) for more targeted Certainty Gap analysis.
    *   **Metadata Changes**: `min_updated_ts` can be used to detect when new market templates are added to the platform.

### Get Markets
*   **Endpoint**: `GET /markets`
*   **Utility**: **Bulk Monitoring & Temporal Urgency.** Returns individual tradable contracts (YES/NO positions) across the entire platform.
    *   **Urgency Sorting**: The `max_close_ts` and `min_close_ts` filters are critical for finding Certainty Gaps that settle soonest, maximizing capital velocity.
    *   **State Tracking**: Allows for bulk checking of market status (`open`, `closed`, `settled`) for a specific set of tickers.
    *   **MVE Control**: Use `mve_filter` to target or exclude complex multivariate events.

### Get Events
*   **Endpoint**: `GET /events`
*   **Utility**: **Master Platform Index.** The primary directory for all non-multivariate activity.
    *   **Broad Discovery**: The only way to get a complete inventory of every active topic on the platform. Essential for discovering high-interest "one-off" events that fall outside standard category filters.
    *   **Event-Level Liquidity**: Shows aggregated volume/heat for entire topics, identifying where the most trading activity is concentrated.
    *   **Implementation Efficiency**: Setting `with_nested_markets=true` allows a single call to populate a full "Certainty Gap" scanner by returning all market data (prices, volume, open interest) within each event.
    *   **Milestone Monitoring**: Use `with_milestones=true` to track real-world progress associated with an event.

### Get Multivariate Events
*   **Endpoint**: `GET /events/multivariate`
*   **Utility**: **Alpha Hunting (Complex Markets).** Fetches "combo" or multivariate events that are excluded from the standard events list. These markets often have lower efficiency and less competition, potentially surfacing "hidden" Certainty Gaps in complex outcome structures.

### Get Multivariate Event Collection
*   **Endpoint**: `GET /multivariate_event_collections/{collection_ticker}`
*   **Utility**: **MVE Source of Truth (Rules & Logic).** The multivariate equivalent of the `Series` endpoint. Returns the definitive logic and settlement criteria for a collection of combo events. Essential for "Hunter" scripts to verify the complex settlement rules of a multivariate Certainty Gap before recommending a trade.

### Get Multivariate Event Collections
*   **Endpoint**: `GET /multivariate_event_collections`
*   **Utility**: **MVE Template Discovery.** Lists all available templates for combo/multivariate markets. Essential for high-level scouting tools to identify new complex market structures (e.g., "Economic Combo" templates) that may contain inefficiently priced Certainty Gaps.

### Get Event
*   **Endpoint**: `GET /events/{event_ticker}`
*   **Utility**: **Event Drill-Down & Distribution Mapping.** Returns detailed data for a specific event and its constituent markets.
    *   **Full Distribution**: Allows "Hunter" scripts to map the entire probability distribution of an event (e.g., all 5 interest rate hike buckets) to find mispriced gaps.
    *   **Arbitrage Analysis**: Critical for events where `mutually_exclusive=true` to calculate if the sum of all outcomes deviates from $1.00.
    *   **Nested Markets**: Use `with_nested_markets=true` for a surgical look at real-time liquidity and prices for every individual market in the event.

### Get Event Metadata
*   **Endpoint**: `GET /events/{event_ticker}/metadata`
*   **Utility**: **Source Audit & Trust Verification.** Returns the definitive list of **Settlement Sources** (official URLs/Institutions) for an event. Crucial for "Hunter" scripts to provide the exact data sources needed for a final manual thesis check before trade execution.

### Get Market
*   **Endpoint**: `GET /markets/{ticker}`
*   **Utility**: **Surgical Verification.** The final "Magnifying Glass" check for a specific binary outcome. Returns the detailed YES/NO positions, current prices, and volume for a single market.
    *   **Entity Resolution**: If `strike_type` is `structured`, the `custom_strike` field contains a **Structured Target ID**. This ID must be resolved via the Structured Targets API to get the human-readable entity name (e.g., resolving a UUID to "Lakers").

## 4. Market Analysis & Sentiment (Live Data)

### Get Market Candlesticks
*   **Endpoint**: `GET /series/{series_ticker}/markets/{ticker}/candlesticks`
*   **Utility**: **Trend Analysis & Entry Timing.** Provides OHLC (Open, High, Low, Close) data for active markets. Essential for identifying "Drift Velocity"—whether a market is steadily climbing toward 99¢ or is stagnant/volatile. Used to prioritize high-momentum Certainty Gaps.

### Batch Get Market Candlesticks
*   **Endpoint**: `GET /markets/candlesticks`
*   **Utility**: **Batch Drift Analysis.** Fetches OHLC data for up to 100 markets in a single request. Essential for high-performance "Drift Monitor" tools that need to analyze momentum for dozens of candidates across the platform simultaneously.

### Get Event Candlesticks
*   **Endpoint**: `GET /series/{series_ticker}/events/{ticker}/candlesticks`
*   **Utility**: **Distribution Shift Analysis.** Provides aggregated OHLC history for **every market** within an event. Critical for understanding how the entire probability distribution shifts over time (e.g., "Which outcome gained probability when the leader dropped from 95¢ to 80¢?"). More efficient than individual market calls for complex events.

### Get Event Forecast Percentile History
*   **Endpoint**: `GET .../events/{ticker}/forecast_percentile_history`
*   **Utility**: **Numerical Consensus & Early Warning.** Converts market prices into a single-number "Crowd Forecast" (e.g., "The median forecast for CPI is 3.1%").
    *   **Consensus Positioning**: Essential for identifying if the crowd's "expected value" is safely centered in your Certainty Gap range or dangerously close to the strike boundary (the "exit").
    *   **Leading Indicator**: Used as a sentiment monitor to see if the numerical forecast is moving away from your strike *before* the market price reflects the increased risk.

### Get Multivariate Event Collection Lookup History
*   **Endpoint**: `GET /multivariate_event_collections/{ticker}/lookup`
*   **Utility**: **Crowd Attention Heat Map.** Tracks which specific "Combo" markets within a collection are being actively researched by other traders.
    *   **Pre-Momentum Detection**: Frequent lookups serve as a leading indicator of interest. Used to identify emerging Certainty Gaps in complex markets before high-volume trading or price shifts occur.

### Get Trades
*   **Endpoint**: `GET /markets/trades`
*   **Utility**: **Liquidity & Spike Validation.** Provides raw transaction history (price, quantity, timestamp). Essential for:
    *   **Momentum Confirmation**: Identifying if a price move (e.g., 70¢ → 90¢) is supported by high volume (broad consensus) or low volume (flash spike).
    *   **Catalyst Detection**: Sudden bursts in trade frequency often signal a real-world news event, making the "Certainty Gap" thesis stronger as the market re-prices to a new high-probability floor.

### Get Market Orderbook
*   **Endpoint**: `GET /markets/{ticker}/orderbook`
*   **Utility**: **Execution Depth & Spread Analysis.** Returns live Bid depth for both YES and NO sides.
    *   **YES Ask Calculation**: To find the real-time cost for a YES Taker order, calculate `$1.00 - Best NO Bid`.
    *   **Liquidity Wall**: Essential for "Hunter" scripts to verify if a market has enough depth to absorb a position without moving the price.
    *   **Maker Strategy**: Identifies the length of the queue at the current Bid, helping decide whether to join as a Maker or "Pay the Ask."

### Get Multiple Market Orderbooks
*   **Endpoint**: `GET /markets/orderbooks`
*   **Utility**: **Batch Performance.** Fetches up to 100 order books in a single request. Essential for high-performance scanners (like `certainty_gap_scanner.py`) to verify real-time depth and spreads for multiple candidates simultaneously without hitting rate limits.

## 5. Live Data & Milestone Monitoring

### Get Live Data (Milestone)
*   **Endpoint**: `GET /live_data/milestone/{milestone_id}`
*   **Utility**: **Real-World "Ground Truth" Scouting.** Provides the live, raw data feed for a specific market milestone (e.g., "Current vote count", "Current score", "Current rainfall").
    *   **Event Grouping**: Use the milestone's `related_event_tickers` to identify all events tied to the same real-world occurrence. This allows "Hunter" scripts to find "correlated Certainty Gaps" across multiple events driven by the same catalyst.
    *   **Execution Trigger**: Used to detect when the real-world outcome is confirmed *before* the market price adjusts.
    *   **Sentiment Verification**: Compares the market's "Crowd Forecast" against the actual, unfolding live data to identify mispriced opportunities.

### Get Multiple Live Data (Batch)
*   **Endpoint**: `GET /live_data/batch`
*   **Utility**: **High-Performance Milestone Monitoring.** Fetches live data for up to 100 milestones in a single request. Essential for "Hunter" scripts that monitor multiple potential Certainty Gaps simultaneously, ensuring no news-driven opportunity is missed due to API latency.

### Get Milestone
*   **Endpoint**: `GET /milestones/{milestone_id}`
*   **Utility**: **Milestone Definition & Rule Context.** Provides metadata for a specific real-world event trigger. Essential for "Hunter" scripts to explain the **why** behind a potential catalyst (e.g., "This milestone represents the official release of the BLS Jobs report"). Used to provide users with clear context on what real-world event will close the current Certainty Gap.

## 6. Profitability Analysis

### Get Series Fee Changes
*   **Endpoint**: `GET /series/fee_changes`
*   **Utility**: **Net ROI Calculation.** Tracks current transaction costs. Essential for distinguishing between profitable trades and those where fees erode the edge.

### Get Incentives
*   **Endpoint**: `GET /incentive_programs`
*   **Utility**: **Profit Multiplier.** Identifies active reward programs. Used to calculate the "Effective Entry Price" (Price minus incentive rebate).

### Fee & Settlement Rounding Rules
*   **Cent Alignment**: All account balances must be exact multiples of $0.01.
*   **Rounding Fee**: A sub-cent adjustment ($0.0000 - $0.0099) applied to entry/exit to restore cent alignment.
*   **Settlement Haircut**: At resolution, payouts are **rounded down** to the nearest cent. The fractional remainder is kept as a settlement fee. 
*   **Fee Accumulator**: Rounding is tracked per order across all fills. Once accumulated overpayment exceeds $0.01, a rebate is issued. This ensures that multiple small fills of a single order converge to the cost of a single equivalent fill.
*   **Implication**: For high-confidence Certainty Gaps (90–96¢), scripts should account for the "Settlement Haircut" and potential rounding fees to provide a true "Floor ROI."

## 7. Real-Time Streaming (WebSockets)

### Connection & Authentication
*   **URL**: `wss://api.elections.kalshi.com/trade-api/ws/v2`
*   **Handshake**: Requires API Key headers (`KALSHI-ACCESS-KEY`, etc.). Even public channels require an authenticated connection.
*   **Method**: `GET` (handshake signature uses `/trade-api/ws/v2`).

### Client Commands (Send)
*   `subscribe`: Subscribe to one or more channels (e.g., `trade`, `ticker`).
*   `unsubscribe`: Cancel existing subscriptions.
*   `list_subscriptions`: Retrieve all active session subscriptions.
*   `update_subscription`: Add or remove specific market tickers from a channel without resubscribing to the entire feed.

### Server Responses (Receive)
*   `subscribed`: Confirmation of successful subscription.
*   `unsubscribed`: Confirmation of successful cancellation.
*   `ok`: Generic success response for update operations.
*   `list_subscriptions`: Payload containing active channels/tickers.
*   `error`: Standardized error message containing `code` and `msg`.

### Critical Strategy Channels
| Channel | Utility for Certainty Gaps |
| :--- | :--- |
| `ticker` | **Price Sniping**: Sub-second updates on bid/ask changes. Used to catch 80-96¢ entries the moment they appear. |
| `trade` | **The Tape**: Real-time feed of all transactions. Essential for the high-performance "Tape Scanner" to detect consensus spikes instantly. |
| `orderbook_delta` | **Queue Monitoring**: Real-time updates to market depth. Used to see if the "Maker" queue at 96¢ is moving or stagnant. |
| `market_lifecycle_v2`| **Close Alerts**: Instant notification when a market closes or settles. |

## 8. Historical Data (Backtesting & Validation)

### Data Partitioning Architecture
To maintain platform performance, Kalshi partitions data into **Live** (approx. last 3 months) and **Historical** tiers. 
*   **Active Boundary**: The division is defined by timestamps retrieved via `GET /historical/cutoff`.
*   **Discovery Impact**: `GET /events` with `with_nested_markets=true` **excludes** markets older than the cutoff. "Hunter" scripts analyzing older events must explicitly query historical endpoints.
*   **Pagination**: Historical endpoints support the same cursor-based pagination as live endpoints.

### Get Historical Cutoff Timestamps
*   **Endpoint**: `GET /historical/cutoff`
*   **Utility**: **System Critical.** The "Master Switch" required to route queries.
    *   `market_settled_ts`: Markets/Candlesticks older than this are in Historical.
    *   `trades_created_ts`: Trades/Fills older than this are in Historical.
    *   `orders_updated_ts`: Completed orders older than this are in Historical.

### Get Historical Markets
*   **Endpoint**: `GET /historical/markets`
*   **Utility**: **Strategy Discovery.** Allows filtering and listing archived markets to build a pool of candidates for Certainty Gap backtesting.

### Get Historical Market Candlesticks
*   **Endpoint**: `GET /historical/markets/{ticker}/candlesticks`
*   **Utility**: **Behavioral Analysis.** Essential for mapping the "Drift" (OHLC data) of archived markets to calculate success rates.

### Get Historical Trades
*   **Endpoint**: `GET /historical/trades`
*   **Utility**: **Liquidity Validation.** Provides granular transaction data for archived markets to verify past tradability.

## 10. Market Lifecycle & State Transitions

### Status Mapping & Filtering
| REST Status | API Filter | Meaning for "Hunter" Scripts |
| :--- | :--- | :--- |
| `active` | `open` | **Tradable**. The only state valid for Certainty Gap entries. |
| `inactive` | `paused` | Temporarily paused. All resting orders are cancelled upon reactivation. |
| `closed` | `closed` | Past `close_time`. No new orders; awaiting determination. |
| `determined` | `closed` | Result known; `settlement_timer_seconds` is counting down. |
| `finalized` | `settled` | **Payout Complete**. Capital is returned to balance. |

### Chronology & Timing (ROI Critical)
*   **`open_time`**: When the market begins trading.
*   **`close_time`**: When trading stops. 
*   **`expected_expiration_time`**: **Definitive Payout Forecast**. This is the field that should be used for Annualized ROI Velocity, as it represents when the outcome is expected to be known.
*   **`latest_expiration_time`**: The hard legal deadline for resolution.
*   **`settlement_timer_seconds`**: The duration of the post-determination dispute window. Capital remains locked during this period.

### Operational Constraints
*   **Post-Close**: Once `close_time` passes, all operations (including cancellations) are rejected with `MARKET_INACTIVE`. 
*   **Early Closure**: If `can_close_early` is true, the `close_time` can be moved earlier by the exchange (often triggered by a Milestone).
