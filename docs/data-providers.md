# Data Providers

DEGIRO Portfolio supports multiple data providers for fetching historical stock prices. You can choose the provider that best fits your needs.

## Available Providers

### Yahoo Finance (Default)

**Free** • No API key required • Global coverage

Yahoo Finance is the default provider and works out of the box with no configuration.

**Pros:**
- Free to use
- No API key required
- Good coverage for US and European stocks
- No rate limits

**Cons:**
- End-of-day data only
- Occasional reliability issues
- No official API support

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
| **Rate Limits** | None | Generous | 800/day (free) |
| **Reliability** | ⚠️ Variable | ✅ Excellent | ✅ Good |
| **Historical Data** | ✅ Many years | ✅ Extensive | ✅ Good |
| **Support** | None | ✅ Official | ✅ Official |

## Switching Providers

To switch providers, simply update your `.env` file:

```bash
# Change from Yahoo to FMP
PRICE_DATA_PROVIDER=fmp
FMP_API_KEY=your_api_key_here
```

Then re-fetch prices:

```bash
uv run invoke fetch-prices
```

The application will automatically use the new provider for all future price fetches.

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
- Switch to Yahoo Finance (no limits)

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
