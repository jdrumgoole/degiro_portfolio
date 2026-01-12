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

from src.degiro_portfolio.database import get_db, Stock, Transaction, StockPrice, Index, IndexPrice, init_db
from src.degiro_portfolio.config import Config, get_column

# NOTE: Hard-coded ticker mappings have been replaced by automatic resolution
# via ticker_resolver.py. Tickers are now stored in the database and resolved
# automatically during import. See ticker_resolver.py for manual fallback mappings.

app = FastAPI(title="DEGIRO Portfolio", version="0.1.0")


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
    def __init__(self, stock: Stock, shares: int, transactions_count: int):
        self.id = stock.id
        self.symbol = stock.symbol
        self.name = stock.name
        self.isin = stock.isin
        self.currency = stock.currency
        self.shares = shares
        self.transactions_count = transactions_count

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "name": self.name,
            "isin": self.isin,
            "currency": self.currency,
            "shares": self.shares,
            "transactions_count": self.transactions_count
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
            holdings.append(StockInfo(stock, int(total_qty), trans_count).to_dict())

    return {"holdings": holdings}


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
                "fees_eur": t.fees_eur or 0
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

    # Calculate position value as percentage of cumulative investment
    position_percentage = []
    if prices and transactions:
        cumulative_shares = 0
        cumulative_invested = 0

        # Build transaction lookup by date
        trans_by_date = {}
        for t in transactions:
            date_key = t.date.strftime("%Y-%m-%d")
            if date_key not in trans_by_date:
                trans_by_date[date_key] = []
            trans_by_date[date_key].append(t)

        for price in prices:
            price_date = price.date.strftime("%Y-%m-%d")

            # Update cumulative shares and investment for any transactions on or before this date
            for trans_date, trans_list in trans_by_date.items():
                if trans_date <= price_date:
                    for t in trans_list:
                        cumulative_shares += t.quantity
                        if t.quantity > 0:  # Only count buy transactions for investment
                            cumulative_invested += abs(t.total_eur)
                    # Remove processed transactions
                    del trans_by_date[trans_date]
                    break

            # Calculate current value and percentage
            if cumulative_invested > 0 and cumulative_shares > 0:
                current_value = price.close * cumulative_shares
                percentage = (current_value / cumulative_invested) * 100
                position_percentage.append({
                    "date": price_date,
                    "percentage": percentage,
                    "invested": cumulative_invested,
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

            for _, row in df.iterrows():
                # Get or create stock
                isin = row[get_column('isin')]
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

                # Parse date
                date_value = row[get_column('date')]
                if isinstance(date_value, str):
                    trans_date = datetime.strptime(date_value, '%d-%m-%Y %H:%M')
                else:
                    trans_date = date_value

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
                        time=trans_date.strftime('%H:%M') if isinstance(trans_date, datetime) else '',
                        quantity=int(row[get_column('quantity')]),
                        price=float(row[get_column('price')]),
                        currency=row[get_column('currency')],
                        value_eur=float(row[get_column('value_eur')]),
                        total_eur=float(row[get_column('total_eur')]),
                        venue='',
                        exchange_rate=None,
                        fees_eur=None,
                        transaction_id=''
                    )
                    db.add(transaction)
                    new_transactions += 1

            db.commit()

            return JSONResponse(
                content={
                    "success": True,
                    "message": f"Successfully imported {new_transactions} new transactions for {updated_stocks} stocks"
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


@app.post("/api/update-market-data")
async def update_market_data(db: Session = Depends(get_db)):
    """Fetch latest market data for all stocks and indices."""
    try:
        updated_stocks = 0
        updated_indices = 0
        errors = []

        # Update stock prices
        stocks = db.query(Stock).all()

        for stock in stocks:
            try:
                # Get ticker symbol from database
                ticker_symbol = stock.yahoo_ticker

                if not ticker_symbol:
                    errors.append(f"No ticker resolved for {stock.name} (ISIN: {stock.isin})")
                    continue

                # Get latest price data (last 7 days to ensure we have recent data)
                ticker = yf.Ticker(ticker_symbol)
                hist = ticker.history(period="7d")

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
                            open=float(row['Open']),
                            high=float(row['High']),
                            low=float(row['Low']),
                            close=float(row['Close']),
                            volume=int(row['Volume']),
                            currency=stock.currency
                        )
                        db.add(price)
                        new_prices += 1

                if new_prices > 0:
                    updated_stocks += 1

            except Exception as e:
                errors.append(f"Error updating {stock.name}: {str(e)}")

        # Update indices
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

        message = f"Updated {updated_stocks} stocks and {updated_indices} indices"
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
