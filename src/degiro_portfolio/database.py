"""Database models and connection for the stockchart application."""
from datetime import datetime
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Database configuration - check environment variable first (for testing)
def get_database_url():
    """Get database URL, checking environment variable each time for test isolation."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        # Default: Database in project root (two directories up from this file)
        db_path = os.path.join(os.path.dirname(__file__), "..", "..", "degiro_portfolio.db")
        database_url = f"sqlite:///{os.path.abspath(db_path)}"
    return database_url

DATABASE_URL = get_database_url()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def reinitialize_engine():
    """Reinitialize the database engine (for testing)."""
    global engine, SessionLocal, DATABASE_URL
    DATABASE_URL = get_database_url()
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Stock(Base):
    """Stock metadata."""
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True)  # Original symbol from transaction data
    name = Column(String)
    isin = Column(String, unique=True, index=True)
    exchange = Column(String)
    currency = Column(String, default="EUR")  # Native trading currency
    yahoo_ticker = Column(String, nullable=True)  # Resolved Yahoo Finance ticker symbol
    data_provider = Column(String, nullable=True)  # Price data provider: 'yahoo', 'twelvedata', 'fmp'

    transactions = relationship("Transaction", back_populates="stock")
    prices = relationship("StockPrice", back_populates="stock")


class Transaction(Base):
    """Stock transaction history."""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"))
    date = Column(DateTime, index=True)
    time = Column(String)
    quantity = Column(Integer)
    price = Column(Float)  # Price in original currency
    currency = Column(String)  # Currency for the price (EUR, USD, SEK, etc.)
    value_eur = Column(Float)
    total_eur = Column(Float)
    venue = Column(String)
    exchange_rate = Column(Float, nullable=True)
    fees_eur = Column(Float, nullable=True)
    transaction_id = Column(String)  # Not unique - same order can have multiple fills

    stock = relationship("Stock", back_populates="transactions")


class StockPrice(Base):
    """Historical stock price data."""
    __tablename__ = "stock_prices"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"))
    date = Column(DateTime, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Integer)
    currency = Column(String, default="EUR")  # Currency for price data

    stock = relationship("Stock", back_populates="prices")


class Index(Base):
    """Market index metadata."""
    __tablename__ = "indices"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True)  # e.g., ^GSPC, ^STOXX50E
    name = Column(String)  # e.g., S&P 500, Euro Stoxx 50

    prices = relationship("IndexPrice", back_populates="index")


class IndexPrice(Base):
    """Historical index price data."""
    __tablename__ = "index_prices"

    id = Column(Integer, primary_key=True, index=True)
    index_id = Column(Integer, ForeignKey("indices.id"))
    date = Column(DateTime, index=True)
    close = Column(Float)

    index = relationship("Index", back_populates="prices")


def init_db():
    """Initialize the database, creating all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
