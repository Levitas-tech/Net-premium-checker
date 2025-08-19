from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
from datetime import datetime
from app.config import settings
import boto3
from typing import Optional, Dict, Any
import json

# Database setup - Using PostgreSQL
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# SQLite engine (commented out for now)
# sqlite_engine = create_engine(settings.SQLITE_DATABASE_URL)
# SQLiteSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to portfolios
    portfolios = relationship("Portfolio", back_populates="user")

class Portfolio(Base):
    __tablename__ = "portfolios"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="portfolios")
    option_legs = relationship("OptionLeg", back_populates="portfolio", cascade="all, delete-orphan")

class OptionLeg(Base):
    __tablename__ = "option_legs"
    
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    index_name = Column(String, nullable=False)
    strike = Column(Float, nullable=False)
    option_type = Column(String, nullable=False)  # CE or PE
    expiry = Column(DateTime, nullable=False)
    action = Column(String, nullable=False)  # Buy or Sell
    lots = Column(Integer, nullable=False, default=1)
    saved_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to portfolio
    portfolio = relationship("Portfolio", back_populates="option_legs")

class LivePrice(Base):
    __tablename__ = "live_prices"
    
    symbol = Column(String, primary_key=True, index=True)
    price = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    trade_symbol = Column(String)  # NIFTY or SENSEX
    strike_price = Column(Float)
    option_type = Column(String)  # CE or PE
    source = Column(String)
    zerodha_price = Column(Float)
    zerodha_timestamp = Column(DateTime)
    instrument_token = Column(Integer, index=True)
    expiry_date = Column(DateTime)

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_sqlite_db():
    """Get SQLite database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# AWS DynamoDB setup - Commented out for now
# class AWSDatabase:
#     def __init__(self):
#         self.dynamodb = boto3.resource(
#             'dynamodb',
#             aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
#             aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
#             region_name=settings.AWS_REGION
#         )
#         self.table = self.dynamodb.Table(settings.AWS_DYNAMODB_TABLE)
#     
#     def save_option_leg(self, user_id: int, leg_data: Dict[str, Any]) -> bool:
#         """Save option leg to AWS DynamoDB"""
#         try:
#             item = {
#                 'id': f"{user_id}_{datetime.now().timestamp()}",
#                 'user_id': user_id,
#                 'index_name': leg_data['index_name'],
#                 'strike': leg_data['strike'],
#                 'option_type': leg_data['option_type'],
#                 'expiry': leg_data['expiry'].isoformat(),
#                 'action': leg_data['action'],
#                 'lots': leg_data['lots'],
#                 'timestamp': datetime.now().isoformat()
#             }
#             
#             self.table.put_item(Item=item)
#             return True
#         except Exception as e:
#             print(f"Error saving to AWS: {e}")
#             return False
#     
#     def get_user_legs(self, user_id: int) -> list:
#         """Get all option legs for a user from AWS"""
#         try:
#             response = self.table.scan(
#                 FilterExpression='user_id = :user_id',
#                 ExpressionAttributeValues={':user_id': user_id}
#             )
#             return response.get('Items', [])
#         except Exception as e:
#             print(f"Error getting legs from AWS: {e}")
#             return []

# Historical backtesting models
class HistoricalBacktest(Base):
    __tablename__ = "historical_backtests"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    backtest_date = Column(DateTime, nullable=False)
    status = Column(String, default="running")  # running, completed, failed
    net_premium_start = Column(Float, nullable=True)
    net_premium_end = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User")
    legs = relationship("HistoricalBacktestLeg", back_populates="backtest", cascade="all, delete-orphan")
    results = relationship("HistoricalBacktestResult", back_populates="backtest", cascade="all, delete-orphan")

class HistoricalBacktestLeg(Base):
    __tablename__ = "historical_backtest_legs"
    
    id = Column(Integer, primary_key=True, index=True)
    backtest_id = Column(Integer, ForeignKey("historical_backtests.id"))
    index_name = Column(String, nullable=False)
    strike = Column(Float, nullable=False)
    option_type = Column(String, nullable=False)  # CE or PE
    expiry = Column(DateTime, nullable=False)
    action = Column(String, nullable=False)  # Buy or Sell
    lots = Column(Integer, nullable=False, default=1)
    
    # Relationships
    backtest = relationship("HistoricalBacktest", back_populates="legs")

class HistoricalBacktestResult(Base):
    __tablename__ = "historical_backtest_results"
    
    id = Column(Integer, primary_key=True, index=True)
    backtest_id = Column(Integer, ForeignKey("historical_backtests.id"))
    datetime = Column(DateTime, nullable=False, index=True)
    net_premium = Column(Float, nullable=False)
    leg_values = Column(Text, nullable=True)  # JSON string of leg_id -> value
    volume = Column(Integer, nullable=True)
    
    # Relationships
    backtest = relationship("HistoricalBacktest", back_populates="results")


# Initialize AWS database - Mock for now
class MockAWSDatabase:
    def save_option_leg(self, user_id: int, leg_data: Dict[str, Any]) -> bool:
        print(f"Mock: Would save option leg to AWS for user {user_id}")
        return True
    
    def get_user_legs(self, user_id: int) -> list:
        print(f"Mock: Would get option legs from AWS for user {user_id}")
        return []

aws_db = MockAWSDatabase() 