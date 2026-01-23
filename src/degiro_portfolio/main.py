"""FastAPI application for stock price visualization."""
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime
from collections import Counter
import json
import os
import pandas as pd
import tempfile
import yfinance as yf

from .database import get_db, Stock, Transaction, StockPrice, Index, IndexPrice, ExchangeRate, init_db
from .config import Config, get_column
from .fetch_prices import fetch_stock_prices
from .price_fetchers import get_price_fetcher, yahoo_rate_limiter
from .ticker_resolver import resolve_ticker_from_isin

# Market indices to track
INDICES = {
    "^GSPC": "S&P 500",
    "^STOXX50E": "Euro Stoxx 50"
}

# NOTE: Hard-coded ticker mappings have been replaced by automatic resolution
# via ticker_resolver.py. Tickers are now stored in the database and resolved
# automatically during import. See ticker_resolver.py for manual fallback mappings.


def ensure_indices_exist(db: Session) -> tuple[int, int]:
    """
    Ensure market indices exist in database and have historical data.
    Returns tuple of (indices_created, prices_fetched).
    """
    indices_created = 0
    prices_fetched = 0

    try:
        for symbol, name in INDICES.items():
            # Check if index exists
            index = db.query(Index).filter_by(symbol=symbol).first()
            if not index:
                index = Index(symbol=symbol, name=name)
                db.add(index)
                db.flush()
                indices_created += 1

            # Check if we have price data
            existing_prices = db.query(IndexPrice).filter_by(index_id=index.id).count()
            if existing_prices == 0:
                # Apply rate limiting before Yahoo call
                yahoo_rate_limiter.wait_if_needed()

                # Fetch historical data (5 years)
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="5y")

                if not hist.empty:
                    # Store prices
                    for date, row in hist.iterrows():
                        price = IndexPrice(
                            index_id=index.id,
                            date=date.to_pydatetime(),
                            close=float(row['Close'])
                        )
                        db.add(price)
                        prices_fetched += 1

        db.commit()

    except Exception as e:
        db.rollback()
        print(f"Error fetching indices: {e}")
        raise

    return indices_created, prices_fetched


app = FastAPI(title="DEGIRO Portfolio", version="0.3.8")

# Track server start time
SERVER_START_TIME = datetime.now()


@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    init_db()


@app.get("/api/ping")
async def ping():
    """Health check endpoint returning server name and uptime."""
    uptime_seconds = (datetime.now() - SERVER_START_TIME).total_seconds()

    # Format uptime as human-readable string
    days, remainder = divmod(int(uptime_seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    if days > 0:
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
    elif hours > 0:
        uptime_str = f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        uptime_str = f"{minutes}m {seconds}s"
    else:
        uptime_str = f"{seconds}s"

    return {
        "status": "ok",
        "server": "DEGIRO Portfolio",
        "version": app.version,
        "started": SERVER_START_TIME.isoformat(),
        "uptime_seconds": uptime_seconds,
        "uptime": uptime_str
    }


# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Models for API responses
class StockInfo:
    """Stock information with current holdings."""
    def __init__(self, stock: Stock, shares: int, transactions_count: int, latest_price=None, price_change_pct=None, price_date=None, price_currency=None):
        self.id = stock.id
        self.symbol = stock.symbol
        self.name = stock.name
        self.isin = stock.isin
        self.currency = stock.currency  # DEGIRO transaction currency
        self.price_currency = price_currency or stock.currency  # Actual price currency from exchange
        self.shares = shares
        self.transactions_count = transactions_count
        self.latest_price = latest_price
        self.price_change_pct = price_change_pct
        self.price_date = price_date
        self.exchange = stock.exchange
        self.yahoo_ticker = stock.yahoo_ticker

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "name": self.name,
            "isin": self.isin,
            "currency": self.price_currency,  # Return actual price currency
            "degiro_currency": self.currency,  # Keep DEGIRO currency for reference
            "shares": self.shares,
            "transactions_count": self.transactions_count,
            "latest_price": self.latest_price,
            "price_change_pct": self.price_change_pct,
            "price_date": self.price_date,
            "exchange": self.exchange,
            "yahoo_ticker": self.yahoo_ticker
        }


@app.get("/")
async def root():
    """Serve the main page."""
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    return FileResponse(index_path)


@app.get("/api/holdings")
async def get_holdings(db: Session = Depends(get_db)):
    """Get all current stock holdings.

    Optimized to use bulk queries instead of N+1 pattern.
    """
    from collections import defaultdict

    # Single query to get all stocks with their holdings and transaction counts
    # This replaces N individual queries with one aggregation query
    holdings_data = db.query(
        Stock,
        func.sum(Transaction.quantity).label('total_qty'),
        func.count(Transaction.id).label('trans_count')
    ).join(Transaction, Stock.id == Transaction.stock_id).group_by(Stock.id).all()

    if not holdings_data:
        return {"holdings": []}

    # Filter to stocks with positive holdings
    active_holdings = [(stock, int(qty), count) for stock, qty, count in holdings_data if qty and qty > 0]

    if not active_holdings:
        return {"holdings": []}

    # Get stock IDs for bulk price fetch
    stock_ids = [stock.id for stock, _, _ in active_holdings]

    # Bulk fetch latest prices using a subquery to get max date per stock
    from sqlalchemy import and_
    from sqlalchemy.orm import aliased

    # Subquery to get the latest date for each stock
    latest_date_subq = db.query(
        StockPrice.stock_id,
        func.max(StockPrice.date).label('max_date')
    ).filter(StockPrice.stock_id.in_(stock_ids)).group_by(StockPrice.stock_id).subquery()

    # Join to get full price records for latest dates
    latest_prices = db.query(StockPrice).join(
        latest_date_subq,
        and_(
            StockPrice.stock_id == latest_date_subq.c.stock_id,
            StockPrice.date == latest_date_subq.c.max_date
        )
    ).all()

    # Build lookup dict: stock_id -> latest price record
    latest_price_by_stock = {p.stock_id: p for p in latest_prices}

    # Bulk fetch second-latest prices for change calculation
    # Get the second max date per stock
    second_latest_subq = db.query(
        StockPrice.stock_id,
        func.max(StockPrice.date).label('second_max_date')
    ).filter(
        StockPrice.stock_id.in_(stock_ids)
    ).filter(
        ~StockPrice.date.in_(
            db.query(latest_date_subq.c.max_date).filter(
                latest_date_subq.c.stock_id == StockPrice.stock_id
            )
        )
    ).group_by(StockPrice.stock_id).subquery()

    previous_prices = db.query(StockPrice).join(
        second_latest_subq,
        and_(
            StockPrice.stock_id == second_latest_subq.c.stock_id,
            StockPrice.date == second_latest_subq.c.second_max_date
        )
    ).all()

    # Build lookup dict: stock_id -> previous price record
    prev_price_by_stock = {p.stock_id: p for p in previous_prices}

    # Build response
    holdings = []
    for stock, total_qty, trans_count in active_holdings:
        latest_price_record = latest_price_by_stock.get(stock.id)

        latest_price = None
        price_change_pct = None
        price_date = None
        price_currency = None

        if latest_price_record:
            latest_price = latest_price_record.close
            price_date = latest_price_record.date.strftime("%Y-%m-%d")
            price_currency = latest_price_record.currency

            prev_price_record = prev_price_by_stock.get(stock.id)
            if prev_price_record and prev_price_record.close > 0:
                price_change_pct = ((latest_price - prev_price_record.close) / prev_price_record.close) * 100

        holdings.append(StockInfo(
            stock,
            total_qty,
            trans_count,
            latest_price,
            price_change_pct,
            price_date,
            price_currency
        ).to_dict())

    return {"holdings": holdings}


@app.get("/api/market-data-status")
async def get_market_data_status(db: Session = Depends(get_db)):
    """Get the most recent market data date."""
    # Get most recent price date across all stocks
    latest_price = db.query(StockPrice).order_by(StockPrice.date.desc()).first()

    if latest_price:
        return {
            "latest_date": latest_price.date.strftime("%Y-%m-%d"),
            "has_data": True
        }
    else:
        return {
            "latest_date": None,
            "has_data": False
        }


@app.get("/api/exchange-rates")
async def get_exchange_rates(db: Session = Depends(get_db)):
    """Get current exchange rates for currency conversion.

    Uses cached rates from the database if available for today.
    Only fetches from Yahoo Finance if rates are missing or stale.
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    currencies = ["USD", "GBP", "SEK"]
    rates = {"EUR": 1.0}
    need_fetch = []

    # Check database for today's cached rates
    for currency in currencies:
        cached_rate = db.query(ExchangeRate).filter(
            ExchangeRate.from_currency == currency,
            ExchangeRate.to_currency == "EUR",
            ExchangeRate.date >= today
        ).first()

        if cached_rate:
            rates[currency] = cached_rate.rate
        else:
            need_fetch.append(currency)

    # Fetch missing rates from Yahoo Finance
    if need_fetch:
        yahoo_symbols = {
            "USD": "USDEUR=X",
            "GBP": "GBPEUR=X",
            "SEK": "SEKEUR=X"
        }

        for currency in need_fetch:
            try:
                # Apply rate limiting before Yahoo call
                yahoo_rate_limiter.wait_if_needed()

                ticker = yf.Ticker(yahoo_symbols[currency])
                hist = ticker.history(period='5d')  # Get 5 days in case of weekends/holidays
                if not hist.empty:
                    rate = float(hist['Close'].iloc[-1])
                    rates[currency] = rate

                    # Store in database for caching
                    exchange_rate = ExchangeRate(
                        date=today,
                        from_currency=currency,
                        to_currency="EUR",
                        rate=rate
                    )
                    db.add(exchange_rate)
                else:
                    # Use fallback if Yahoo returns no data
                    rates[currency] = _get_fallback_rate(currency)
            except Exception as e:
                error_msg = str(e).lower()
                if 'rate' in error_msg or 'too many' in error_msg:
                    yahoo_rate_limiter.report_rate_limit()
                rates[currency] = _get_fallback_rate(currency)

        try:
            db.commit()
        except Exception:
            db.rollback()

    return {
        "success": True,
        "rates": rates,
        "cached": len(need_fetch) == 0
    }


def _get_fallback_rate(currency: str) -> float:
    """Get fallback exchange rate for a currency."""
    fallbacks = {
        "USD": 0.85,
        "SEK": 0.093,
        "GBP": 1.18
    }
    return fallbacks.get(currency, 1.0)


@app.get("/api/stock/{stock_id}/prices")
async def get_stock_prices(stock_id: int, db: Session = Depends(get_db)):
    """Get historical prices for a stock."""
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    prices = db.query(StockPrice).filter_by(stock_id=stock_id).order_by(StockPrice.date).all()

    return {
        "stock": {
            "id": stock.id,
            "name": stock.name,
            "symbol": stock.symbol,
            "currency": stock.currency
        },
        "prices": [
            {
                "date": p.date.strftime("%Y-%m-%d"),
                "open": p.open,
                "high": p.high,
                "low": p.low,
                "close": p.close,
                "volume": p.volume,
                "currency": p.currency
            }
            for p in prices
        ]
    }


@app.get("/api/stock/{stock_id}/transactions")
async def get_stock_transactions(stock_id: int, db: Session = Depends(get_db)):
    """Get transaction history for a stock."""
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    transactions = db.query(Transaction).filter_by(stock_id=stock_id).order_by(Transaction.date).all()

    return {
        "stock": {
            "id": stock.id,
            "name": stock.name,
            "symbol": stock.symbol,
            "currency": stock.currency
        },
        "transactions": [
            {
                "id": t.id,
                "date": t.date.strftime("%Y-%m-%d %H:%M"),
                "quantity": t.quantity,
                "price": t.price,
                "currency": t.currency,
                "total_eur": t.total_eur,
                "fees_eur": t.fees_eur or 0,
                "transaction_type": "buy" if t.quantity > 0 else "sell"
            }
            for t in transactions
        ]
    }


@app.get("/api/stock/{stock_id}/chart-data")
async def get_chart_data(stock_id: int, db: Session = Depends(get_db)):
    """Get chart data for a stock including prices and transactions."""
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Get price data
    prices = db.query(StockPrice).filter_by(stock_id=stock_id).order_by(StockPrice.date).all()

    # Get transactions
    transactions = db.query(Transaction).filter_by(stock_id=stock_id).order_by(Transaction.date).all()

    # Calculate running position
    running_position = []
    total_shares = 0
    for t in transactions:
        total_shares += t.quantity
        running_position.append({
            "date": t.date.strftime("%Y-%m-%d"),
            "shares": total_shares,
            "transaction_type": "buy" if t.quantity > 0 else "sell",
            "quantity": abs(t.quantity),
            "price": t.price,
            "currency": t.currency
        })

    # Get index data for comparison
    indices_data = []
    if prices:
        start_date = prices[0].date
        end_date = prices[-1].date

        # Get S&P 500 and Euro Stoxx 50
        indices = db.query(Index).all()
        for index in indices:
            index_prices = db.query(IndexPrice).filter(
                IndexPrice.index_id == index.id,
                IndexPrice.date >= start_date,
                IndexPrice.date <= end_date
            ).order_by(IndexPrice.date).all()

            if index_prices:
                # Normalize to percentage change from first price
                base_price = index_prices[0].close
                normalized = [
                    {
                        "date": ip.date.strftime("%Y-%m-%d"),
                        "normalized": ((ip.close - base_price) / base_price) * 100
                    }
                    for ip in index_prices
                ]

                indices_data.append({
                    "name": index.name,
                    "symbol": index.symbol,
                    "data": normalized
                })

        # Also normalize stock prices for comparison
        if prices:
            base_stock_price = prices[0].close
            stock_normalized = [
                {
                    "date": p.date.strftime("%Y-%m-%d"),
                    "normalized": ((p.close - base_stock_price) / base_stock_price) * 100
                }
                for p in prices
            ]
        else:
            stock_normalized = []

    else:
        stock_normalized = []

    # Calculate position value as percentage of net investment (buys - sells)
    # Optimized: use incremental approach instead of modifying dict during iteration
    position_percentage = []
    if prices and transactions:
        # Sort transactions by date for incremental processing
        sorted_trans = sorted(transactions, key=lambda t: t.date)
        trans_idx = 0
        cumulative_shares = 0
        net_invested = 0.0

        # Pre-compute exchange rate lookup (most recent rate up to each date)
        exchange_rate_by_date = {}
        last_rate = None
        for t in sorted_trans:
            if t.exchange_rate:
                last_rate = t.exchange_rate
            exchange_rate_by_date[t.date.strftime("%Y-%m-%d")] = last_rate

        for price in prices:
            price_date = price.date.strftime("%Y-%m-%d")

            # Process all transactions up to this price date (incremental)
            while trans_idx < len(sorted_trans) and sorted_trans[trans_idx].date.strftime("%Y-%m-%d") <= price_date:
                t = sorted_trans[trans_idx]
                cumulative_shares += t.quantity
                # Net invested = buys - sells
                if t.quantity > 0:  # Buy
                    net_invested += abs(t.total_eur)
                else:  # Sell
                    net_invested -= abs(t.total_eur)
                trans_idx += 1

            # Calculate current value with proper currency conversion
            if net_invested > 0 and cumulative_shares > 0:
                # Convert price to EUR using actual exchange currency
                if price.currency == 'EUR':
                    price_eur = price.close
                else:
                    # Get most recent exchange rate
                    exchange_rate = None
                    for t_date in sorted(exchange_rate_by_date.keys(), reverse=True):
                        if t_date <= price_date and exchange_rate_by_date[t_date]:
                            exchange_rate = exchange_rate_by_date[t_date]
                            break

                    if exchange_rate:
                        price_eur = price.close / exchange_rate
                    else:
                        # Fallback: treat as EUR equivalent
                        price_eur = price.close

                current_value = price_eur * cumulative_shares
                percentage = (current_value / net_invested) * 100
                position_percentage.append({
                    "date": price_date,
                    "percentage": percentage,
                    "invested": net_invested,
                    "value": current_value
                })

    return {
        "stock": {
            "id": stock.id,
            "name": stock.name,
            "symbol": stock.symbol,
            "currency": stock.currency,
            "data_provider": stock.data_provider or "unknown"
        },
        "prices": [
            {
                "date": p.date.strftime("%Y-%m-%d"),
                "close": p.close,
                "high": p.high,
                "low": p.low,
                "open": p.open,
                "currency": p.currency
            }
            for p in prices
        ],
        "transactions": running_position,
        "indices": indices_data,
        "stock_normalized": stock_normalized,
        "position_percentage": position_percentage
    }


@app.get("/api/portfolio-performance")
async def get_portfolio_performance(db: Session = Depends(get_db)):
    """Get percentage return performance for all currently held stocks.

    Optimized to fetch all data in bulk queries.
    """
    from collections import defaultdict

    # Fetch all data in bulk
    stocks = {s.id: s for s in db.query(Stock).all()}
    all_transactions = db.query(Transaction).order_by(Transaction.date).all()
    all_prices = db.query(StockPrice).order_by(StockPrice.date).all()

    # Group transactions by stock
    trans_by_stock = defaultdict(list)
    holdings_by_stock = defaultdict(int)
    for t in all_transactions:
        trans_by_stock[t.stock_id].append(t)
        holdings_by_stock[t.stock_id] += t.quantity

    # Group prices by stock
    prices_by_stock = defaultdict(list)
    for p in all_prices:
        prices_by_stock[p.stock_id].append(p)

    portfolio_data = []

    for stock_id, stock in stocks.items():
        total_qty = holdings_by_stock.get(stock_id, 0)

        if total_qty <= 0:
            continue

        transactions = trans_by_stock.get(stock_id, [])

        # Calculate weighted average cost for currently held shares
        buy_transactions = [t for t in transactions if t.quantity > 0]
        if not buy_transactions:
            continue

        total_spent = sum(abs(t.total_eur) for t in buy_transactions)
        total_shares_bought = sum(t.quantity for t in buy_transactions)

        if total_shares_bought == 0:
            continue

        avg_cost_per_share = total_spent / total_shares_bought

        # Get price history (already sorted by date)
        prices = prices_by_stock.get(stock_id, [])

        if not prices:
            continue

        # Calculate percentage return for each date
        performance = []
        for price in prices:
            # Return = (current_price - avg_cost) / avg_cost * 100
            percent_return = ((price.close - avg_cost_per_share) / avg_cost_per_share) * 100
            performance.append({
                "date": price.date.strftime("%Y-%m-%d"),
                "return": percent_return
            })

        portfolio_data.append({
            "stock_id": stock.id,
            "name": stock.name,
            "symbol": stock.symbol,
            "currency": stock.currency,
            "shares": int(total_qty),
            "performance": performance
        })

    return {"stocks": portfolio_data}


@app.get("/api/portfolio-valuation-history")
async def get_portfolio_valuation_history(db: Session = Depends(get_db)):
    """
    Get historical portfolio valuation over time.
    Returns dates, net invested capital (buys - sells), and portfolio values (all in EUR).
    Shows only from the first purchase of currently held stocks.

    Optimized to pre-fetch all data and calculate incrementally.
    """
    from datetime import datetime
    from collections import defaultdict

    # Get all transactions ordered by date
    all_transactions = db.query(Transaction).order_by(Transaction.date).all()

    if not all_transactions:
        return {"dates": [], "invested": [], "values": []}

    # Get all stocks as a dict for quick lookup
    stocks = {s.id: s for s in db.query(Stock).all()}

    # Group transactions by stock and calculate current holdings
    trans_by_stock = defaultdict(list)
    current_holdings = defaultdict(int)
    for t in all_transactions:
        trans_by_stock[t.stock_id].append(t)
        current_holdings[t.stock_id] += t.quantity

    # Find stocks with current holdings > 0
    current_stock_ids = {sid for sid, qty in current_holdings.items() if qty > 0}

    if not current_stock_ids:
        return {"dates": [], "invested": [], "values": []}

    # Find earliest transaction for currently held stocks
    first_trans_date = min(
        t.date for t in all_transactions if t.stock_id in current_stock_ids
    )

    # Get all unique dates from price history after first transaction
    price_dates = db.query(StockPrice.date).filter(
        StockPrice.date >= first_trans_date
    ).distinct().order_by(StockPrice.date).all()

    if not price_dates:
        return {"dates": [], "invested": [], "values": []}

    # Convert to list of dates
    date_list = [pd[0] for pd in price_dates]

    # Add today if not present
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if today > date_list[-1]:
        date_list.append(today)

    # Pre-fetch ALL prices into memory - keyed by (stock_id, date)
    all_prices = db.query(StockPrice).filter(
        StockPrice.date >= first_trans_date
    ).all()

    # Build price lookup: for each stock, sorted list of (date, price, currency)
    price_by_stock = defaultdict(list)
    for p in all_prices:
        price_by_stock[p.stock_id].append((p.date, p.close, p.currency))

    # Sort prices by date for each stock
    for stock_id in price_by_stock:
        price_by_stock[stock_id].sort(key=lambda x: x[0])

    # Pre-compute exchange rates by stock (most recent rate from transactions)
    exchange_rates_by_stock = {}
    for stock_id, trans_list in trans_by_stock.items():
        for t in reversed(trans_list):
            if t.exchange_rate:
                exchange_rates_by_stock[stock_id] = t.exchange_rate
                break

    # Build transaction events sorted by date for incremental calculation
    # Each event: (date, stock_id, quantity_delta, invested_delta)
    trans_events = []
    for t in all_transactions:
        if t.stock_id in current_stock_ids:
            invested_delta = abs(t.total_eur) if t.quantity > 0 else -abs(t.total_eur)
            trans_events.append((t.date, t.stock_id, t.quantity, invested_delta))
    trans_events.sort(key=lambda x: x[0])

    # Calculate series incrementally
    dates = []
    invested_series = []
    value_series = []

    # Running state
    running_invested = 0.0
    running_holdings = defaultdict(int)  # stock_id -> quantity
    event_idx = 0

    for price_date in date_list:
        # Process all transactions up to this date
        while event_idx < len(trans_events) and trans_events[event_idx][0] <= price_date:
            _, stock_id, qty_delta, inv_delta = trans_events[event_idx]
            running_holdings[stock_id] += qty_delta
            running_invested += inv_delta
            event_idx += 1

        # Calculate portfolio value using pre-fetched prices
        total_value_eur = 0.0

        for stock_id, holdings in running_holdings.items():
            if holdings <= 0:
                continue

            # Binary search for most recent price <= price_date
            prices = price_by_stock.get(stock_id, [])
            if not prices:
                continue

            # Find the last price on or before price_date
            price_close = None
            price_currency = None
            for p_date, p_close, p_currency in reversed(prices):
                if p_date <= price_date:
                    price_close = p_close
                    price_currency = p_currency
                    break

            if price_close is None:
                continue

            # Convert to EUR if needed
            if price_currency == 'EUR':
                price_eur = price_close
            else:
                exchange_rate = exchange_rates_by_stock.get(stock_id)
                if exchange_rate:
                    price_eur = price_close / exchange_rate
                else:
                    price_eur = price_close  # Fallback

            total_value_eur += holdings * price_eur

        dates.append(price_date.strftime("%Y-%m-%d"))
        invested_series.append(round(running_invested, 2))
        value_series.append(round(total_value_eur, 2))

    return {
        "dates": dates,
        "invested": invested_series,
        "values": value_series
    }


@app.post("/api/upload-transactions")
async def upload_transactions(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload and process a new transactions Excel file."""
    try:
        # Validate file type
        if not file.filename.endswith(('.xlsx', '.xls')):
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Please upload an Excel file (.xlsx or .xls)"}
            )

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        try:
            # Read Excel file
            df = pd.read_excel(tmp_file_path)

            # Validate required columns using config
            is_valid, missing_columns = Config.validate_excel_columns(df.columns.tolist())
            if not is_valid:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": f"Missing required columns: {', '.join(missing_columns)}"}
                )

            # Helper function to determine native currency
            def determine_native_currency(df_data, product):
                product_col = get_column('product')
                currency_col = get_column('currency')
                product_df = df_data[df_data[product_col] == product]
                currency_counts = Counter(product_df[currency_col].values)
                if currency_counts:
                    return currency_counts.most_common(1)[0][0]
                return "EUR"

            # Process transactions
            new_transactions = 0
            updated_stocks = 0
            stocks_to_fetch_prices = set()  # Track stocks that need price fetching

            for _, row in df.iterrows():
                # Check if stock is in the ignore list
                isin = row[get_column('isin')]
                if isin in Config.IGNORED_STOCKS:
                    continue  # Skip ignored stocks

                # Get or create stock
                stock = db.query(Stock).filter_by(isin=isin).first()

                if not stock:
                    product_name = row[get_column('product')]
                    native_currency = determine_native_currency(df, product_name)
                    stock = Stock(
                        symbol=product_name.split()[0] if product_name else isin,
                        name=product_name,
                        isin=isin,
                        exchange=row[get_column('exchange')],
                        currency=native_currency
                    )
                    db.add(stock)
                    db.flush()
                    updated_stocks += 1
                    stocks_to_fetch_prices.add(stock.id)  # Track new stock for price fetching
                else:
                    stocks_to_fetch_prices.add(stock.id)  # Also fetch for existing stocks if needed

                # Parse date and time (DEGIRO exports have separate columns)
                date_str = str(row[get_column('date')])
                time_str = str(row[get_column('time')])

                # Combine date and time strings
                datetime_str = f"{date_str} {time_str}"
                trans_date = datetime.strptime(datetime_str, "%d-%m-%Y %H:%M")

                # Check if transaction already exists
                existing_trans = db.query(Transaction).filter(
                    Transaction.stock_id == stock.id,
                    Transaction.date == trans_date,
                    Transaction.quantity == int(row[get_column('quantity')]),
                    Transaction.price == float(row[get_column('price')])
                ).first()

                if not existing_trans:
                    transaction = Transaction(
                        stock_id=stock.id,
                        date=trans_date,
                        time=time_str,
                        quantity=int(row[get_column('quantity')]),
                        price=float(row[get_column('price')]),
                        currency=row[get_column('currency')],
                        value_eur=float(row[get_column('value_eur')]),
                        total_eur=float(row[get_column('total_eur')]),
                        venue=row[get_column('venue')] if get_column('venue') in row else '',
                        exchange_rate=float(row[get_column('exchange_rate')]) if get_column('exchange_rate') in row and pd.notna(row[get_column('exchange_rate')]) else None,
                        fees_eur=float(row[get_column('fees_eur')]) if get_column('fees_eur') in row and pd.notna(row[get_column('fees_eur')]) else None,
                        transaction_id=str(row[get_column('transaction_id')]) if get_column('transaction_id') in row else ''
                    )
                    db.add(transaction)
                    new_transactions += 1

            db.commit()

            # After successful import, fetch historical prices for NEW stocks and update latest prices
            total_prices = 0
            stocks_with_prices = 0

            if stocks_to_fetch_prices:
                print(f"\n📈 Fetching prices for {len(stocks_to_fetch_prices)} stocks...")

                for stock_id in stocks_to_fetch_prices:
                    stock = db.query(Stock).filter_by(id=stock_id).first()
                    if stock:
                        # Fetch historical prices if we haven't already fetched for this stock
                        existing_prices = db.query(StockPrice).filter_by(stock_id=stock.id).count()
                        if existing_prices == 0:
                            price_count = fetch_stock_prices(stock, db)
                            if price_count > 0:
                                total_prices += price_count
                                stocks_with_prices += 1

            # Also refresh live prices if FMP is configured
            live_prices_updated = 0
            if Config.PRICE_DATA_PROVIDER == 'fmp':
                from .price_fetchers import FMPFetcher
                fetcher = FMPFetcher()

                # Get currently held stocks
                all_stocks = db.query(Stock).all()
                for stock in all_stocks:
                    total_qty = db.query(func.sum(Transaction.quantity)).filter_by(
                        stock_id=stock.id
                    ).scalar() or 0
                    if total_qty > 0 and stock.yahoo_ticker:
                        # Fetch latest quote
                        quote = fetcher.fetch_latest_quote(stock.yahoo_ticker)
                        if quote and quote.get('price'):
                            # Update or insert latest price in database
                            quote_date = datetime.strptime(quote['timestamp'], '%Y-%m-%d') if isinstance(quote['timestamp'], str) else quote['timestamp']

                            # Check if we already have this date
                            existing = db.query(StockPrice).filter_by(
                                stock_id=stock.id,
                                date=quote_date
                            ).first()

                            if existing:
                                # Update existing record
                                existing.open = quote['open']
                                existing.high = quote['high']
                                existing.low = quote['low']
                                existing.close = quote['price']
                                existing.volume = quote['volume']
                            else:
                                # Insert new record
                                new_price = StockPrice(
                                    stock_id=stock.id,
                                    date=quote_date,
                                    open=quote['open'],
                                    high=quote['high'],
                                    low=quote['low'],
                                    close=quote['price'],
                                    volume=quote['volume'],
                                    currency=stock.currency
                                )
                                db.add(new_price)

                            live_prices_updated += 1
                            db.commit()

            # Ensure indices exist and fetch data if needed
            indices_created, index_prices_fetched = ensure_indices_exist(db)

            # Update market data for all indices
            indices_updated = 0
            indices = db.query(Index).all()
            for index in indices:
                try:
                    # Apply rate limiting before Yahoo call
                    yahoo_rate_limiter.wait_if_needed()

                    ticker = yf.Ticker(index.symbol)
                    hist = ticker.history(period="7d")

                    if not hist.empty:
                        new_prices = 0
                        for date, row in hist.iterrows():
                            price_date = date.to_pydatetime().replace(hour=0, minute=0, second=0, microsecond=0)

                            existing = db.query(IndexPrice).filter(
                                IndexPrice.index_id == index.id,
                                IndexPrice.date == price_date
                            ).first()

                            if not existing:
                                price = IndexPrice(
                                    index_id=index.id,
                                    date=price_date,
                                    close=float(row['Close'])
                                )
                                db.add(price)
                                new_prices += 1

                        if new_prices > 0:
                            indices_updated += 1
                            db.commit()

                except Exception as e:
                    print(f"Error updating index {index.name}: {e}")

            message = f"Successfully imported {new_transactions} new transactions"
            if updated_stocks > 0:
                message += f" for {updated_stocks} new stocks"
            if total_prices > 0:
                message += f", fetched {total_prices} historical price records"
            if live_prices_updated > 0:
                message += f", and updated {live_prices_updated} live prices"
            if indices_created > 0:
                message += f", created {indices_created} market indices"
            if index_prices_fetched > 0:
                message += f", fetched {index_prices_fetched} index price records"
            if indices_updated > 0:
                message += f", and updated {indices_updated} market indices"

            return JSONResponse(
                content={
                    "success": True,
                    "message": message
                }
            )

        finally:
            # Clean up temporary file
            os.unlink(tmp_file_path)

    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error processing file: {str(e)}"}
        )


@app.post("/api/refresh-live-prices")
async def refresh_live_prices(db: Session = Depends(get_db)):
    """Fetch real-time price quotes for currently held stocks using Twelve Data or Yahoo Finance.

    Optimized to use bulk query for holdings calculation.
    """
    try:
        from .price_fetchers import get_price_fetcher
        from .fetch_prices import YAHOO_FINANCE_OVERRIDE
        import yfinance as yf

        # Bulk query to get stocks with positive holdings (single query instead of N queries)
        holdings_query = db.query(
            Stock,
            func.sum(Transaction.quantity).label('total_qty')
        ).join(Transaction, Stock.id == Transaction.stock_id).group_by(Stock.id).having(
            func.sum(Transaction.quantity) > 0
        ).all()

        current_holdings = [stock for stock, qty in holdings_query]

        # Fetch quotes for all holdings
        quotes = []
        errors = []

        # Try Twelve Data first if configured, otherwise use Yahoo Finance
        use_twelvedata = Config.PRICE_DATA_PROVIDER == 'twelvedata'

        for stock in current_holdings:
            ticker_symbol = stock.yahoo_ticker
            if not ticker_symbol:
                errors.append(f"No ticker for {stock.name}")
                continue

            quote_data = None

            # Check if this stock is in the Yahoo Finance override list
            force_yahoo = ticker_symbol in YAHOO_FINANCE_OVERRIDE

            # Try Twelve Data real-time quote first if configured and not overridden
            if use_twelvedata and not force_yahoo:
                try:
                    fetcher = get_price_fetcher('twelvedata')
                    quote_data = fetcher.fetch_latest_quote(ticker_symbol)
                except Exception as e:
                    print(f"  ⚠️  Twelve Data quote failed for {stock.name}, trying Yahoo Finance: {e}")

            # Fallback to Yahoo Finance if Twelve Data not configured or failed
            if not quote_data:
                try:
                    # Apply rate limiting before Yahoo call
                    yahoo_rate_limiter.wait_if_needed()

                    ticker_obj = yf.Ticker(ticker_symbol)
                    hist = ticker_obj.history(period='1d')

                    if hist.empty:
                        errors.append(f"No quote for {stock.name}")
                        continue

                    # Get latest data
                    latest = hist.iloc[-1]
                    prev_close = ticker_obj.info.get('previousClose', latest['Close'])

                    # Calculate change
                    change = latest['Close'] - prev_close
                    change_percent = (change / prev_close * 100) if prev_close else 0

                    # Get actual currency
                    actual_currency = ticker_obj.info.get('currency', stock.currency)

                    quote_data = {
                        "price": float(latest['Close']),
                        "change": float(change),
                        "change_percent": float(change_percent),
                        "open": float(latest['Open']),
                        "high": float(latest['High']),
                        "low": float(latest['Low']),
                        "volume": int(latest['Volume']),
                        "timestamp": hist.index[-1].strftime('%Y-%m-%d %H:%M:%S'),
                    }
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'rate' in error_msg or 'too many' in error_msg:
                        yahoo_rate_limiter.report_rate_limit()
                    errors.append(f"Error fetching {stock.name}: {str(e)}")
                    continue

            if quote_data:
                quotes.append({
                    "stock_id": stock.id,
                    "name": stock.name,
                    "symbol": stock.symbol,
                    "ticker": ticker_symbol,
                    "price": quote_data['price'],
                    "change": quote_data.get('change', 0),
                    "change_percent": quote_data.get('change_percent', 0),
                    "open": quote_data.get('open', 0),
                    "high": quote_data.get('high', 0),
                    "low": quote_data.get('low', 0),
                    "volume": quote_data.get('volume', 0),
                    "timestamp": quote_data.get('timestamp', ''),
                    "currency": stock.currency
                })

        return JSONResponse(
            content={
                "success": True,
                "quotes": quotes,
                "count": len(quotes),
                "errors": errors,
                "timestamp": datetime.now().isoformat(),
                "provider": "twelvedata" if use_twelvedata else "yahoo"
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error fetching live prices: {str(e)}"}
        )


@app.post("/api/update-market-data")
async def update_market_data(db: Session = Depends(get_db)):
    """Fetch latest market data for currently held stocks and indices.

    Optimized to use bulk query for holdings calculation.
    """
    try:
        updated_stocks = 0
        updated_indices = 0
        errors = []

        # Get price fetcher based on configuration
        fetcher = get_price_fetcher()
        provider = Config.PRICE_DATA_PROVIDER

        # Bulk query to get stocks with positive holdings (single query instead of N queries)
        holdings_query = db.query(
            Stock,
            func.sum(Transaction.quantity).label('total_qty')
        ).join(Transaction, Stock.id == Transaction.stock_id).group_by(Stock.id).having(
            func.sum(Transaction.quantity) > 0
        ).all()

        current_holdings = [stock for stock, qty in holdings_query]

        for stock in current_holdings:
            try:
                # Get ticker symbol from database, or resolve if missing
                ticker_symbol = stock.yahoo_ticker

                if not ticker_symbol:
                    # Try to auto-resolve the ticker
                    ticker_symbol = resolve_ticker_from_isin(stock.isin, stock.currency)
                    if ticker_symbol:
                        # Save resolved ticker to database
                        stock.yahoo_ticker = ticker_symbol
                        db.commit()
                    else:
                        errors.append(f"No ticker resolved for {stock.name} (ISIN: {stock.isin})")
                        continue

                # Get latest price data (last 7 days to ensure we have recent data)
                end_date = datetime.now()
                start_date = end_date - pd.Timedelta(days=7)

                hist = fetcher.fetch_prices(ticker_symbol, start_date, end_date)

                # If primary provider returns no data, fall back to Yahoo Finance
                if hist.empty and provider != 'yahoo':
                    try:
                        from .price_fetchers import YahooFinanceFetcher
                        yahoo_fetcher = YahooFinanceFetcher()
                        hist = yahoo_fetcher.fetch_prices(ticker_symbol, start_date, end_date)
                    except Exception:
                        pass

                if hist.empty:
                    errors.append(f"No data available for {stock.name}")
                    continue

                # Add new price records
                new_prices = 0
                for date, row in hist.iterrows():
                    price_date = date.to_pydatetime().replace(hour=0, minute=0, second=0, microsecond=0)

                    # Check if price already exists
                    existing = db.query(StockPrice).filter(
                        StockPrice.stock_id == stock.id,
                        StockPrice.date == price_date
                    ).first()

                    if not existing:
                        price = StockPrice(
                            stock_id=stock.id,
                            date=price_date,
                            open=float(row['open']),
                            high=float(row['high']),
                            low=float(row['low']),
                            close=float(row['close']),
                            volume=int(row['volume']),
                            currency=stock.currency
                        )
                        db.add(price)
                        new_prices += 1

                if new_prices > 0:
                    updated_stocks += 1

            except Exception as e:
                errors.append(f"Error updating {stock.name}: {str(e)}")

        # Update indices (still using yfinance directly as it's always Yahoo Finance symbols)
        indices = db.query(Index).all()
        for index in indices:
            try:
                # Apply rate limiting before Yahoo call
                yahoo_rate_limiter.wait_if_needed()

                ticker = yf.Ticker(index.symbol)
                hist = ticker.history(period="7d")

                if hist.empty:
                    errors.append(f"No data for {index.name}")
                    continue

                new_prices = 0
                for date, row in hist.iterrows():
                    price_date = date.to_pydatetime().replace(hour=0, minute=0, second=0, microsecond=0)

                    existing = db.query(IndexPrice).filter(
                        IndexPrice.index_id == index.id,
                        IndexPrice.date == price_date
                    ).first()

                    if not existing:
                        price = IndexPrice(
                            index_id=index.id,
                            date=price_date,
                            close=float(row['Close'])
                        )
                        db.add(price)
                        new_prices += 1

                if new_prices > 0:
                    updated_indices += 1

            except Exception as e:
                error_msg = str(e).lower()
                if 'rate' in error_msg or 'too many' in error_msg:
                    yahoo_rate_limiter.report_rate_limit()
                errors.append(f"Error updating {index.name}: {str(e)}")

        db.commit()

        message = f"Updated {updated_stocks} stocks and {updated_indices} indices using {provider}"
        if errors:
            message += f" ({len(errors)} errors)"

        return JSONResponse(
            content={
                "success": True,
                "message": message,
                "stocks_updated": updated_stocks,
                "indices_updated": updated_indices,
                "errors": errors
            }
        )

    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error updating market data: {str(e)}"}
        )


@app.post("/api/purge-database")
async def purge_database(db: Session = Depends(get_db)):
    """Purge all data from the database (stocks, transactions, prices, indices).

    WARNING: This is a destructive operation that cannot be undone!
    """
    try:
        # Count records before deletion
        stock_count = db.query(Stock).count()
        transaction_count = db.query(Transaction).count()
        price_count = db.query(StockPrice).count()
        index_count = db.query(Index).count()
        index_price_count = db.query(IndexPrice).count()

        # Delete all data in correct order (foreign key constraints)
        db.query(StockPrice).delete()
        db.query(Transaction).delete()
        db.query(Stock).delete()
        db.query(IndexPrice).delete()
        db.query(Index).delete()

        db.commit()

        return JSONResponse(
            content={
                "success": True,
                "message": "Database purged successfully",
                "deleted": {
                    "stocks": stock_count,
                    "transactions": transaction_count,
                    "stock_prices": price_count,
                    "indices": index_count,
                    "index_prices": index_price_count
                }
            }
        )

    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error purging database: {str(e)}"}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
