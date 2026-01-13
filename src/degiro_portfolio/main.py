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

from .database import get_db, Stock, Transaction, StockPrice, Index, IndexPrice, init_db
from .config import Config, get_column
from .fetch_prices import fetch_stock_prices
from .price_fetchers import get_price_fetcher

# NOTE: Hard-coded ticker mappings have been replaced by automatic resolution
# via ticker_resolver.py. Tickers are now stored in the database and resolved
# automatically during import. See ticker_resolver.py for manual fallback mappings.

app = FastAPI(title="DEGIRO Portfolio", version="0.2.1")


@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    init_db()


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
    """Get all current stock holdings."""
    stocks = db.query(Stock).all()

    holdings = []
    for stock in stocks:
        total_qty = db.query(func.sum(Transaction.quantity)).filter_by(
            stock_id=stock.id
        ).scalar() or 0

        if total_qty > 0:
            trans_count = db.query(Transaction).filter_by(stock_id=stock.id).count()

            # Get latest and previous prices
            latest_price_record = db.query(StockPrice).filter_by(
                stock_id=stock.id
            ).order_by(StockPrice.date.desc()).first()

            latest_price = None
            price_change_pct = None
            price_date = None
            price_currency = None

            if latest_price_record:
                latest_price = latest_price_record.close
                price_date = latest_price_record.date.strftime("%Y-%m-%d")
                price_currency = latest_price_record.currency  # Get actual price currency

                # Get previous price (day before latest)
                previous_price_record = db.query(StockPrice).filter(
                    StockPrice.stock_id == stock.id,
                    StockPrice.date < latest_price_record.date
                ).order_by(StockPrice.date.desc()).first()

                if previous_price_record and previous_price_record.close > 0:
                    price_change_pct = ((latest_price - previous_price_record.close) / previous_price_record.close) * 100

            holdings.append(StockInfo(
                stock,
                int(total_qty),
                trans_count,
                latest_price,
                price_change_pct,
                price_date,
                price_currency  # Pass actual price currency
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
    position_percentage = []
    if prices and transactions:
        cumulative_shares = 0
        net_invested = 0

        # Build transaction lookup by date
        trans_by_date = {}
        for t in transactions:
            date_key = t.date.strftime("%Y-%m-%d")
            if date_key not in trans_by_date:
                trans_by_date[date_key] = []
            trans_by_date[date_key].append(t)

        for price in prices:
            price_date = price.date.strftime("%Y-%m-%d")

            # Update cumulative shares and net investment for any transactions on or before this date
            for trans_date, trans_list in trans_by_date.items():
                if trans_date <= price_date:
                    for t in trans_list:
                        cumulative_shares += t.quantity
                        # Net invested = buys - sells
                        if t.quantity > 0:  # Buy
                            net_invested += abs(t.total_eur)
                        else:  # Sell
                            net_invested -= abs(t.total_eur)
                    # Remove processed transactions
                    del trans_by_date[trans_date]
                    break

            # Calculate current value with proper currency conversion
            if net_invested > 0 and cumulative_shares > 0:
                # Convert price to EUR using actual exchange currency, not DEGIRO transaction currency
                if price.currency == 'EUR':
                    price_eur = price.close
                else:
                    # Get most recent exchange rate from transactions on or before this date
                    exchange_rate = None
                    for t in transactions:
                        if t.date.strftime("%Y-%m-%d") <= price_date and t.exchange_rate:
                            exchange_rate = t.exchange_rate

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
            "currency": stock.currency
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
    """Get percentage return performance for all currently held stocks."""
    stocks = db.query(Stock).all()

    portfolio_data = []

    for stock in stocks:
        # Check if currently held
        total_qty = db.query(func.sum(Transaction.quantity)).filter_by(
            stock_id=stock.id
        ).scalar() or 0

        if total_qty <= 0:
            continue

        # Get all transactions for this stock
        transactions = db.query(Transaction).filter_by(stock_id=stock.id).order_by(Transaction.date).all()

        # Calculate weighted average cost for currently held shares
        buy_transactions = [t for t in transactions if t.quantity > 0]
        if not buy_transactions:
            continue

        total_spent = sum(abs(t.total_eur) for t in buy_transactions)
        total_shares_bought = sum(t.quantity for t in buy_transactions)

        if total_shares_bought == 0:
            continue

        avg_cost_per_share = total_spent / total_shares_bought

        # Get price history
        prices = db.query(StockPrice).filter_by(stock_id=stock.id).order_by(StockPrice.date).all()

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
    """
    # Get all transactions ordered by date
    all_transactions = db.query(Transaction).order_by(Transaction.date).all()

    if not all_transactions:
        return {"dates": [], "invested": [], "values": []}

    # Get all stocks
    stocks = db.query(Stock).all()

    # Find stocks with current holdings > 0
    current_stock_ids = set()
    for stock in stocks:
        total_qty = sum(t.quantity for t in all_transactions if t.stock_id == stock.id)
        if total_qty > 0:
            current_stock_ids.add(stock.id)

    if not current_stock_ids:
        return {"dates": [], "invested": [], "values": []}

    # Find earliest transaction for currently held stocks
    first_trans_date = min(
        t.date for t in all_transactions if t.stock_id in current_stock_ids
    )

    # Get all unique dates from price history after first transaction of current holdings
    price_dates = db.query(StockPrice.date).filter(
        StockPrice.date >= first_trans_date
    ).distinct().order_by(StockPrice.date).all()

    if not price_dates:
        return {"dates": [], "invested": [], "values": []}

    # Group transactions by stock for efficient lookup
    trans_by_stock = {}
    for t in all_transactions:
        if t.stock_id not in trans_by_stock:
            trans_by_stock[t.stock_id] = []
        trans_by_stock[t.stock_id].append(t)

    dates = []
    invested_series = []
    value_series = []

    for (price_date,) in price_dates:
        # Calculate net invested (buys minus sells) for CURRENTLY HELD stocks only
        buys = sum(
            abs(t.total_eur)
            for t in all_transactions
            if t.date <= price_date and t.quantity > 0 and t.stock_id in current_stock_ids
        )
        sells = sum(
            abs(t.total_eur)
            for t in all_transactions
            if t.date <= price_date and t.quantity < 0 and t.stock_id in current_stock_ids
        )
        net_invested = buys - sells

        # Calculate portfolio value
        total_value_eur = 0

        for stock in stocks:
            # Calculate holdings for this stock at this date
            holdings = sum(
                t.quantity
                for t in trans_by_stock.get(stock.id, [])
                if t.date <= price_date
            )

            if holdings <= 0:
                continue

            # Get price on or before this date
            price_record = db.query(StockPrice).filter(
                StockPrice.stock_id == stock.id,
                StockPrice.date <= price_date
            ).order_by(StockPrice.date.desc()).first()

            if not price_record:
                continue

            # Convert price to EUR using actual exchange currency, not DEGIRO transaction currency
            if price_record.currency == 'EUR':
                price_eur = price_record.close
            else:
                # Get most recent exchange rate from transactions
                exchange_rate = None
                for t in reversed(trans_by_stock.get(stock.id, [])):
                    if t.date <= price_date and t.exchange_rate:
                        exchange_rate = t.exchange_rate
                        break

                if exchange_rate:
                    price_eur = price_record.close / exchange_rate
                else:
                    # Fallback: treat as EUR equivalent
                    price_eur = price_record.close

            total_value_eur += holdings * price_eur

        dates.append(price_date.strftime("%Y-%m-%d"))
        invested_series.append(round(net_invested, 2))
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

            message = f"Successfully imported {new_transactions} new transactions"
            if updated_stocks > 0:
                message += f" for {updated_stocks} new stocks"
            if total_prices > 0:
                message += f", fetched {total_prices} historical price records"
            if live_prices_updated > 0:
                message += f", and updated {live_prices_updated} live prices"

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
    """Fetch real-time price quotes for currently held stocks."""
    try:
        # Use Yahoo Finance for live prices (free, reliable, supports all exchanges)
        import yfinance as yf

        # Get currently held stocks
        all_stocks = db.query(Stock).all()
        current_holdings = []
        for stock in all_stocks:
            total_qty = db.query(func.sum(Transaction.quantity)).filter_by(
                stock_id=stock.id
            ).scalar() or 0
            if total_qty > 0:
                current_holdings.append(stock)

        # Fetch quotes for all holdings
        quotes = []
        errors = []

        for stock in current_holdings:
            ticker_symbol = stock.yahoo_ticker
            if not ticker_symbol:
                errors.append(f"No ticker for {stock.name}")
                continue

            try:
                # Fetch current price from Yahoo Finance
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

                quotes.append({
                    "stock_id": stock.id,
                    "name": stock.name,
                    "symbol": stock.symbol,
                    "ticker": ticker_symbol,
                    "price": float(latest['Close']),
                    "change": float(change),
                    "change_percent": float(change_percent),
                    "open": float(latest['Open']),
                    "high": float(latest['High']),
                    "low": float(latest['Low']),
                    "volume": int(latest['Volume']),
                    "timestamp": hist.index[-1].strftime('%Y-%m-%d'),
                    "currency": actual_currency
                })
            except Exception as e:
                errors.append(f"Error fetching {stock.name}: {str(e)}")

        return JSONResponse(
            content={
                "success": True,
                "quotes": quotes,
                "count": len(quotes),
                "errors": errors,
                "timestamp": datetime.now().isoformat()
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error fetching live prices: {str(e)}"}
        )


@app.post("/api/update-market-data")
async def update_market_data(db: Session = Depends(get_db)):
    """Fetch latest market data for currently held stocks and indices."""
    try:
        updated_stocks = 0
        updated_indices = 0
        errors = []

        # Get price fetcher based on configuration
        fetcher = get_price_fetcher()
        provider = Config.PRICE_DATA_PROVIDER

        # Update stock prices - only for currently held stocks
        all_stocks = db.query(Stock).all()

        # Filter to stocks with current holdings
        current_holdings = []
        for stock in all_stocks:
            total_qty = db.query(func.sum(Transaction.quantity)).filter_by(
                stock_id=stock.id
            ).scalar() or 0

            if total_qty > 0:
                current_holdings.append(stock)

        for stock in current_holdings:
            try:
                # Get ticker symbol from database
                ticker_symbol = stock.yahoo_ticker

                if not ticker_symbol:
                    errors.append(f"No ticker resolved for {stock.name} (ISIN: {stock.isin})")
                    continue

                # Get latest price data (last 7 days to ensure we have recent data)
                end_date = datetime.now()
                start_date = end_date - pd.Timedelta(days=7)

                hist = fetcher.fetch_prices(ticker_symbol, start_date, end_date)

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
