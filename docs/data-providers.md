# Data Providers

## What Are Data Providers?

To show you stock prices and charts, the application needs to download historical price data from the internet. Different websites and services offer this data - these are called "data providers".

**Good news**: The application uses Yahoo Finance, which is free and works great for most people. You don't need to configure anything!

## Yahoo Finance (Default)

**Free** - No API key required - Global coverage

Yahoo Finance is the default provider and works out of the box with no configuration.

**Pros:**
- Free to use
- No API key required
- Good coverage for US and European stocks
- Historical data going back many years

**Cons:**
- End-of-day data only
- Occasional reliability issues
- No official API support
- Has undocumented rate limits (the app handles this automatically)

**Configuration:**
```bash
# .env (optional — yahoo is the default)
PRICE_DATA_PROVIDER=yahoo
```

## Ticker Resolution

DEGIRO transaction exports identify stocks by ISIN, but Yahoo Finance needs a ticker symbol (`SAP.DE`, `SAVE.ST`, `KD`, …). The application resolves the ISIN → ticker mapping automatically the first time it sees a stock, and caches the result in the `yahoo_ticker` column of the `stocks` table.

### How resolution works

When a new stock is imported, `resolve_ticker_from_isin()` tries strategies in order:

1. **Manual override.** A small allowlist (`MANUAL_TICKER_MAPPING` in `src/degiro_portfolio/ticker_resolver.py`) for stocks where a specific listing must be pinned.
2. **Yahoo Finance Search** (`yf.Search(isin)`). The primary resolver. Yahoo indexes most listed equities and ETFs globally by ISIN; the search returns candidate listings across exchanges.
3. **Legacy prefix heuristic.** Last-resort defensive path for US/NL/DE/FR/IT/ES ISINs, kept for offline or network-flaky environments.

### Picking the right listing

The same ISIN can be listed on several Yahoo venues (Stockholm and Stuttgart, Athens and Amsterdam, etc.). To pick the right one, the resolver compares each candidate's suffix against:

1. The stock's **trading currency**. SEK → `.ST`, NOK → `.OL`, CHF → `.SW`, GBP → `.L`, JPY → `.T`, PLN → `.WA`, HKD → `.HK`, AUD → `.AX`, CAD → `.TO`, BRL → `.SA`, INR → `.NS`, … (~30 currencies; USD is intentionally unmapped — US tickers have no suffix).
2. If the currency hint doesn't disambiguate (e.g. EUR is shared across Athens, Amsterdam, Paris, Milan, Madrid, …), the **ISIN country prefix**: `DE` → `.DE`, `FR` → `.PA`, `NL` → `.AS`, `GR` → `.AT`, `IE` → `.IR`, `AT` → `.VI`, `IT` → `.MI`, `ES` → `.MC`, `FI` → `.HE`, `BE` → `.BR`, `PT` → `.LS`, …
3. If neither matches, the first equity/ETF/mutual-fund result wins.

This covers 40+ ISIN country codes across Europe, Asia/Pacific, the Americas, the Middle East, and Africa. The complete maps live in `CURRENCY_TO_SUFFIX` and `COUNTRY_TO_SUFFIX` in `ticker_resolver.py`.

### Examples

| ISIN          | Currency | Resolved ticker | How                                  |
|---------------|----------|-----------------|--------------------------------------|
| SE0015192067  | SEK      | `SAVE.ST`       | Yahoo Search, `.ST` matched currency |
| GRS469003024  | EUR      | `KRI.AT`        | Yahoo Search, `.AT` matched country  |
| CH0024608827  | CHF      | `PGHN.SW`       | Yahoo Search, `.SW` matched currency |
| GB00B1YW4409  | GBP      | `III.L`         | Yahoo Search, `.L` matched currency  |
| JP3389510003  | JPY      | `6544.T`        | Yahoo Search, `.T` matched currency  |
| US50155Q1004  | USD      | `KD`            | Yahoo Search (Kyndryl)               |
| DE0007164600  | EUR      | `SAP.DE`        | Manual override                      |

### Forcing a re-resolve

If you upgraded from a version that couldn't resolve tickers for some markets, clear the cached tickers and trigger a refresh:

```python
from src.degiro_portfolio.database import SessionLocal, Stock
db = SessionLocal()
db.query(Stock).update({Stock.yahoo_ticker: None})
db.commit()
```

Then click **Update Market Data** in the web UI (or `POST /api/update-market-data`).

### Pinning a specific listing

If Yahoo's first result is wrong for a particular stock, add an entry to `MANUAL_TICKER_MAPPING`:

```python
MANUAL_TICKER_MAPPING: Dict[str, Dict[str, str]] = {
    # ... existing mappings ...
    "GB0005405286": {"GBP": "HSBA.L"},  # HSBC Holdings - London
}
```

Manual mappings are checked first, before any network call, and always win.

For deeper internals (full mapping tables, troubleshooting, migration from old hard-coded mappings), see [`TICKER_RESOLUTION.md`](https://github.com/jdrumgoole/degiro-portfolio/blob/main/TICKER_RESOLUTION.md) in the project root.

## Rate Limiting

Yahoo Finance has undocumented rate limits (~2000 requests/hour). The application automatically throttles requests (~20/minute) to stay within limits.

If you see rate limit errors:
- Wait 60 seconds and try again
- Exchange rates are cached daily to reduce API calls
- The app falls back gracefully when limits are hit

## Environment Variables

You can optionally create a `.env` file in the project root:

```bash
PRICE_DATA_PROVIDER=yahoo

# Optional: adjust fetch periods
INITIAL_FETCH_PERIOD=max
INDEX_FETCH_PERIOD=5y
UPDATE_FETCH_PERIOD=7d
```

## Troubleshooting

### "No data returned" for a stock
- Check if the ticker symbol is correct
- The stock might be delisted or only available on regional exchanges
- Try clicking "Update Market Data" again

### Rate limit errors
- Wait 60 seconds and try again
- The app auto-throttles, but rapid manual refreshes can hit limits

## Notes

- Historical data is stored in the local database
- Switching data providers doesn't affect stored data
- You can re-fetch data at any time by clicking "Update Market Data"
