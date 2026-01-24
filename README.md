# Kalshi Platform Snapshot Tool

A Python script to crawl the Kalshi prediction market platform and generate snapshots of all active series and events, grouped by category and sorted by trading volume.

## Purpose

This is the **Level 1: Platform Crawler** from the Kalshi development roadmap. It answers the question: "What exists on this platform and what is actually being traded?"

## Features

- Fetches all series with volume data
- Fetches all events with nested market data (handles pagination automatically)
- Groups data by category
- Sorts by trading volume to identify high-liquidity markets
- Filters out low/no-volume "ghost town" markets
- Multiple output formats: JSON, CSV, and human-readable console output
- Comprehensive statistics and top 20 rankings

## Installation

```bash
# Install required dependency
pip install requests

# Make the script executable (optional)
chmod +x platform_snapshot.py
```

## Usage

### Basic Usage (Console Output)

```bash
python platform_snapshot.py
```

This fetches all open events and displays a formatted summary to the console.

### Save to JSON File

```bash
python platform_snapshot.py --output-format json --output-file snapshot.json
```

### Save to CSV File

```bash
python platform_snapshot.py --output-format csv --output-file snapshot.csv
```

### Filter by Minimum Volume

Filter out events with less than 1,000 contracts traded:

```bash
python platform_snapshot.py --min-volume 1000
```

### Fetch Closed or Settled Events

```bash
python platform_snapshot.py --status closed
python platform_snapshot.py --status settled
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--output-format` | Output format: `json`, `csv`, or `console` | `console` |
| `--min-volume` | Minimum volume threshold for filtering events | `0` |
| `--status` | Event status: `open`, `closed`, or `settled` | `open` |
| `--output-file` | Path to save output (if not specified, prints to stdout) | - |

## Output Format

### Console Output

Provides:
- Metadata summary (timestamp, totals, volume)
- Category statistics sorted by volume
- Top 20 events by volume
- Top 20 series by volume

### JSON Output

Complete structured data including:
- `metadata`: Snapshot metadata and summary statistics
- `series_by_category`: All series grouped by category
- `events_by_category`: All events grouped by category
- `category_statistics`: Aggregated stats per category

### CSV Output

Two CSV sections:
1. **Events**: ticker, title, category, volume, market_count, series_ticker
2. **Series**: ticker, title, category, frequency, volume, tags

## Example Workflow

```bash
# 1. Get a quick overview of the platform
python platform_snapshot.py

# 2. Save detailed data for analysis
python platform_snapshot.py --output-format json -o snapshot_$(date +%Y%m%d).json

# 3. Find high-volume markets only
python platform_snapshot.py --min-volume 5000 -o high_volume.csv --output-format csv

# 4. Compare open vs closed markets
python platform_snapshot.py --status open -o open_events.json --output-format json
python platform_snapshot.py --status closed -o closed_events.json --output-format json
```

## API Endpoints Used

- `GET /series` - Fetches all series with volume data
- `GET /events` - Fetches all events with pagination support

Both endpoints are **public** and do not require authentication.

## Notes

- The script automatically handles pagination for events (max 200 per page)
- Volume is calculated by summing all market volumes within each event
- Categories are extracted from the event data
- Progress messages are printed to stderr, allowing stdout redirection

## Next Steps

After running this snapshot, you can:

1. **Level 1.5**: Drill down into specific events using `GET /events/{ticker}`
2. **Level 2**: Look for arbitrage opportunities in mutually exclusive events
3. **Level 3**: Analyze order book spreads for trading efficiency
4. **Level 4**: Monitor real-time data with `GET /live_data` (requires auth)

## Troubleshooting

**Import Error: No module named 'requests'**
```bash
pip install requests
```

**Timeout Errors**
The script uses a 30-second timeout per request. If the API is slow, you may need to increase this in the code.

**Empty Results**
Check your filters (`--status`, `--min-volume`) - they may be too restrictive.

## License

This is a development tool for the Kalshi API. Use in accordance with Kalshi's Terms of Service.
