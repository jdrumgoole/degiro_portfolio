"""Database models and connection for the stockchart application."""
from datetime import datetime
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Database in project root (two directories up from this file)
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "stockchart.db")
DATABASE_URL = f"sqlite:///{os.path.abspath(DB_PATH)}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Stock(Base):
    """Stock metadata."""
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True)
    name = Column(String)
    isin = Column(String, unique=True, index=True)
    exchange = Column(String)
    currency = Column(String, default="EUR")  # Native trading currency

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
