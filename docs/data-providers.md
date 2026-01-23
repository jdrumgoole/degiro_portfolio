# Data Providers

## What Are Data Providers?

To show you stock prices and charts, the application needs to download historical price data from the internet. Different websites and services offer this data - these are called "data providers".

**Good news**: The application comes configured with Yahoo Finance, which is free and works great for most people. You don't need to change anything unless you want to!

This guide explains the available options if you want to:
- Use a more reliable data source
- Get data for stocks not available on Yahoo Finance
- Access premium features

## Available Providers

**Quick Recommendation**: Unless you have specific needs, stick with Yahoo Finance (the default) - it's free and works well.

### Yahoo Finance (Default)

**Free** • No API key required • Global coverage

Yahoo Finance is the default provider and works out of the box with no configuration.

**Pros:**
- Free to use
- No API key required
- Good coverage for US and European stocks

**Cons:**
- End-of-day data only
- Occasional reliability issues
- No official API support
- Has undocumented rate limits (the app handles this automatically)

**Configuration:**
```bash
# .env
PRICE_DATA_PROVIDER=yahoo
```

### Financial Modeling Prep (FMP)

**Paid** • API key required • Excellent coverage

FMP provides comprehensive financial data with a paid API.

**Pros:**
- Reliable API with official support
- Excellent coverage (US and international stocks)
- Historical data going back many years
- Fast response times
- Support for ADRs and international tickers

**Cons:**
- Requires paid subscription
- API key needed
- Free tier has very limited features

**Configuration:**
```bash
# .env
PRICE_DATA_PROVIDER=fmp
FMP_API_KEY=your_api_key_here
```

**Get an API key:**
1. Visit [Financial Modeling Prep](https://site.financialmodelingprep.com/)
2. Sign up for an account
3. Choose a subscription plan (Starter or higher recommended)
4. Get your API key from the dashboard

**Ticker Handling:**
FMP uses simplified ticker symbols. The application automatically handles conversion:
- `SAP.DE` → `SAP`
- `ASML.AS` → `ASML`
- `IFX.DE` → `IFNNY` (Infineon ADR)
- `ERIC-B.ST` → `ERIC`

### Twelve Data

**Freemium** • API key required • Good coverage

Twelve Data offers a free tier with 800 API calls per day.

**Pros:**
- Free tier available (800 calls/day)
- Good coverage for major stocks
- Clean API
- Real-time data on paid plans

**Cons:**
- Limited free tier
- Some European stocks not available on free tier
- Rate limits on free tier

**Configuration:**
```bash
# .env
PRICE_DATA_PROVIDER=twelvedata
TWELVEDATA_API_KEY=your_api_key_here
```

**Get an API key:**
1. Visit [Twelve Data](https://twelvedata.com/)
2. Sign up for a free account
3. Get your API key from the dashboard

## Comparison Table

| Feature | Yahoo Finance | FMP | Twelve Data |
|---------|---------------|-----|-------------|
| **Cost** | Free | Paid ($14-99/mo) | Free / Paid |
| **API Key** | No | Yes | Yes |
| **US Stocks** | ✅ Excellent | ✅ Excellent | ✅ Excellent |
| **EU Stocks** | ✅ Good | ✅ Excellent | ⚠️ Limited (free) |
| **Rate Limits** | ~20/min (auto-handled) | Generous | 800/day (free) |
| **Reliability** | ⚠️ Variable | ✅ Excellent | ✅ Good |
| **Historical Data** | ✅ Many years | ✅ Extensive | ✅ Good |
| **Support** | None | ✅ Official | ✅ Official |

## How to Switch Providers

**Only do this if you need a different data source than Yahoo Finance.**

### Step 1: Create a Configuration File

1. Find the folder where you installed the application
2. Create a new text file named `.env` (yes, it starts with a dot)
3. Open it in a text editor (Notepad, TextEdit, etc.)

**On Windows**: You may need to save it as `".env"` (with quotes) in Notepad to prevent Windows from adding `.txt` at the end.

### Step 2: Add Your Configuration

Copy and paste one of these into your `.env` file:

**For Yahoo Finance (default, no key needed):**
```bash
PRICE_DATA_PROVIDER=yahoo
```

**For FMP (paid, requires API key):**
```bash
PRICE_DATA_PROVIDER=fmp
FMP_API_KEY=paste_your_api_key_here
```

**For Twelve Data (free tier available):**
```bash
PRICE_DATA_PROVIDER=twelvedata
TWELVEDATA_API_KEY=paste_your_api_key_here
```

### Step 3: Save and Restart

1. Save the `.env` file
2. Stop the server: `degiro_portfolio stop`
3. Start it again: `degiro_portfolio start`
4. Click "📈 Update Market Data" in the web interface to download prices with the new provider

**That's it!** The application will now use your chosen provider for all price data.

## Recommendations

### For Personal Use (Free)
**Use Yahoo Finance**
- No setup required
- Works well for most portfolios
- Good enough for tracking performance

### For Serious Investors
**Use FMP (Paid)**
- More reliable data
- Better coverage
- Official API support
- Worth the cost for portfolio management

### For Development/Testing
**Use Twelve Data (Free Tier)**
- Good for testing
- Clean API
- Reasonable rate limits

## Environment Variables

Create a `.env` file in the project root:

```bash
# Choose your provider
PRICE_DATA_PROVIDER=fmp  # or 'yahoo', 'twelvedata'

# API keys (only if using FMP or Twelve Data)
FMP_API_KEY=your_fmp_key_here
TWELVEDATA_API_KEY=your_twelvedata_key_here

# Optional: adjust fetch periods
INITIAL_FETCH_PERIOD=max
INDEX_FETCH_PERIOD=5y
UPDATE_FETCH_PERIOD=7d
```

See `.env.example` for a complete template.

## Troubleshooting

### "No API key" error
Make sure your `.env` file exists and contains the correct API key for your chosen provider.

### "No data returned" for a stock
- Check if the ticker symbol is correct
- Some providers may not have data for certain stocks
- Try switching to a different provider

### Rate limit errors (Twelve Data)
- Free tier is limited to 800 calls/day
- Wait 24 hours or upgrade to paid plan
- Switch to Yahoo Finance as alternative

### Rate limit errors (Yahoo Finance)
- Yahoo has undocumented rate limits (~2000 requests/hour)
- The app automatically throttles requests (~20/minute) to avoid rate limits
- If you see rate limit errors, wait 60 seconds and try again
- Exchange rates are cached daily to reduce API calls

### 402 Payment Required (FMP)
- Free tier has very limited access
- Upgrade to paid subscription
- Switch to Yahoo Finance for free alternative

## API Costs

### FMP Pricing (as of 2025)
- **Starter**: $14/month - Good for personal portfolios
- **Professional**: $49/month - Advanced features
- **Enterprise**: $99+/month - High volume

### Twelve Data Pricing
- **Free**: 800 calls/day - Good for small portfolios
- **Basic**: $8/month - 3,000 calls/day
- **Pro**: $29/month - Unlimited calls

### Yahoo Finance
- **Free**: No cost, no limits

## Notes

- All providers return data in the same format internally
- Switching providers doesn't affect your stored data
- Historical data remains in the database
- You can re-fetch data with a different provider at any time
