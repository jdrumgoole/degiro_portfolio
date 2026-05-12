# Automatic Ticker Resolution

## Overview

The DEGIRO Portfolio application automatically resolves ISIN codes to Yahoo Finance ticker symbols. This works globally — Swedish, Greek, Swiss, UK, Japanese, Polish, Bulgarian, Luxembourg, and the other ~40 markets Yahoo indexes are all supported out of the box, without code changes.

Tickers are resolved during import (or on first price fetch) and cached in the `yahoo_ticker` column of the `stocks` table.

## How It Works

### Resolution Strategy

`resolve_ticker_from_isin()` in `src/degiro_portfolio/ticker_resolver.py` tries strategies in order:

1. **Manual override** — small allowlist (`MANUAL_TICKER_MAPPING`) for stocks where Yahoo's first result is wrong or a specific listing must be pinned.
2. **Yahoo Finance Search** (`yf.Search(isin)`) — the primary resolver. Yahoo indexes most listed equities and ETFs globally by ISIN. The first equity/ETF/mutual-fund result whose ticker suffix matches the trading currency wins; if no currency match, the ISIN country prefix is used; otherwise the first result.
3. **Legacy prefix heuristic** — last-resort defensive path for US/NL/DE/FR/IT/ES ISINs, kept for offline / network-flaky environments.

### Currency → Suffix Preference

When Yahoo lists the same ISIN on multiple venues (e.g. Stockholm + Stuttgart), the trading currency from your DEGIRO export disambiguates:

| Currency | Suffix | Exchange       |
|----------|--------|----------------|
| SEK      | `.ST`  | Stockholm      |
| NOK      | `.OL`  | Oslo           |
| DKK      | `.CO`  | Copenhagen     |
| CHF      | `.SW`  | SIX Swiss      |
| GBP      | `.L`   | London         |
| JPY      | `.T`   | Tokyo          |
| PLN      | `.WA`  | Warsaw         |
| CZK      | `.PR`  | Prague         |
| HUF      | `.BD`  | Budapest       |
| TRY      | `.IS`  | Istanbul       |
| HKD      | `.HK`  | Hong Kong      |
| AUD      | `.AX`  | Australia      |
| CAD      | `.TO`  | Toronto        |
| BRL      | `.SA`  | São Paulo (B3) |
| INR      | `.NS`  | India NSE      |
| ILS      | `.TA`  | Tel Aviv       |
| ZAR      | `.JO`  | Johannesburg   |
| USD      | *(none)* | US — bare ticker |

Full list: see `CURRENCY_TO_SUFFIX` in `ticker_resolver.py`.

### Country Prefix → Suffix Fallback

When the currency hint is ambiguous (e.g. EUR is shared across Athens, Amsterdam, Paris, Milan, Madrid…), the resolver falls back to the ISIN country prefix:

`GR` → `.AT` (Athens), `DE` → `.DE`, `FR` → `.PA`, `NL` → `.AS`, `IT` → `.MI`, `ES` → `.MC`, `FI` → `.HE`, `BE` → `.BR`, `PT` → `.LS`, `AT` → `.VI`, `IE` → `.IR`, and so on — covering 40+ ISIN country codes across Europe, Asia/Pacific, the Americas, the Middle East, and Africa.

Full list: see `COUNTRY_TO_SUFFIX` in `ticker_resolver.py`.

### Worked Examples

| ISIN          | Currency | Resolved ticker | How                                  |
|---------------|----------|-----------------|--------------------------------------|
| SE0015192067  | SEK      | `SAVE.ST`       | Yahoo Search, `.ST` matched currency |
| GRS469003024  | EUR      | `KRI.AT`        | Yahoo Search, `.AT` matched country  |
| CH0024608827  | CHF      | `PGHN.SW`       | Yahoo Search, `.SW` matched currency |
| GB00B1YW4409  | GBP      | `III.L`         | Yahoo Search, `.L` matched currency  |
| JP3389510003  | JPY      | `6544.T`        | Yahoo Search, `.T` matched currency  |
| PLATPRT00018  | PLN      | `APR.WA`        | Yahoo Search, `.WA` matched currency |
| US50155Q1004  | USD      | `KD`            | Yahoo Search (Kyndryl)               |
| DE0007164600  | EUR      | `SAP.DE`        | Manual override                      |
| NL0010273215  | EUR      | `ASML.AS`       | Manual override                      |

### When It Runs

- **During import** (`/api/upload-transactions`): for every new stock that ends up with a positive net position, `fetch_stock_prices()` calls the resolver and stores the result.
- **On Update Market Data** (`/api/update-market-data`): if a stock still has no `yahoo_ticker`, the endpoint resolves it on demand and caches it.

Once resolved, the ticker is persisted in the database and reused on subsequent runs.

## Manual Overrides

For a stock where Yahoo's first result is wrong, or you need to pin a specific listing, add an entry to `MANUAL_TICKER_MAPPING` in `src/degiro_portfolio/ticker_resolver.py`:

```python
MANUAL_TICKER_MAPPING: Dict[str, Dict[str, str]] = {
    # ... existing mappings ...
    "GB0005405286": {"GBP": "HSBA.L"},  # HSBC Holdings - London
}
```

The mapping is checked first, before any network call, and always wins.

## Database Schema

The `stocks` table includes:

- `symbol` — display label derived from the first word of the DEGIRO product name
- `name` — full company name
- `isin` — ISIN code (unique identifier)
- `exchange` — exchange code from the DEGIRO transaction
- `currency` — DEGIRO trading currency
- **`yahoo_ticker`** — resolved Yahoo Finance ticker (nullable)

## Inspecting Resolved Tickers

```bash
uv run python -m invoke db-info
```

Or directly:

```python
from src.degiro_portfolio.database import SessionLocal, Stock

session = SessionLocal()
for stock in session.query(Stock).all():
    print(f"{stock.name:40} | ISIN: {stock.isin:14} | "
          f"Ticker: {stock.yahoo_ticker or 'NOT RESOLVED'}")
```

## Manually Setting a Ticker

If automatic resolution returns the wrong listing for a specific stock, you can override it directly in the database:

```python
from src.degiro_portfolio.database import SessionLocal, Stock

session = SessionLocal()
stock = session.query(Stock).filter_by(isin="YOUR_ISIN").first()
if stock:
    stock.yahoo_ticker = "TICKER_SYMBOL"
    session.commit()
```

For a permanent override that survives database resets, prefer adding the mapping to `MANUAL_TICKER_MAPPING` instead.

## Troubleshooting

### "Could not automatically resolve ISIN" warning in the logs

Yahoo Search returned no equity/ETF results for the ISIN. Options:

1. Verify the stock exists on https://finance.yahoo.com using its ISIN.
2. Add an entry to `MANUAL_TICKER_MAPPING` with the correct ticker.
3. Set the ticker directly via the database snippet above.

### Wrong listing was picked (e.g. Stuttgart instead of Stockholm)

Yahoo returns multiple listings for some ISINs and the currency/country preference didn't disambiguate cleanly. Pin the correct listing with a `MANUAL_TICKER_MAPPING` entry.

### "No data returned" but the ticker resolved

The ticker resolved, but the price fetcher returned nothing. Usually means the stock is delisted, regionally restricted, or Yahoo simply has no data for that specific listing. Try the ticker manually on https://finance.yahoo.com to confirm.

## Migration from Older Versions

If you upgraded from a release where ticker resolution was limited to US/NL/DE/FR/IT/ES ISINs (so non-Euro European stocks, Asian stocks, etc. had `yahoo_ticker = NULL`), the simplest path is:

```python
# In a Python shell at the project root
from src.degiro_portfolio.database import SessionLocal, Stock
db = SessionLocal()
db.query(Stock).update({Stock.yahoo_ticker: None})
db.commit()
```

Then trigger a market-data refresh from the web UI (or `POST /api/update-market-data`). All held stocks will re-resolve through the new Yahoo Search path. Existing manual overrides are preserved.
