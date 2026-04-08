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
