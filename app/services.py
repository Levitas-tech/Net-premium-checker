from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
from datetime import datetime, date
import psycopg2
from psycopg2.extras import RealDictCursor
from app.database import OptionLeg, LivePrice, aws_db, User, Portfolio
from app.models import OptionLegCreate, OptionLegResponse, PortfolioCreate, PortfolioResponse
from app.config import settings
import logging
from app.database import SessionLocal
import time
import os

logger = logging.getLogger(__name__)

class PortfolioService:
    def __init__(self):
        pass
    
    def create_portfolio(self, db: Session, user_id: int, portfolio_data: PortfolioCreate) -> Portfolio:
        """Create a new portfolio for a user"""
        portfolio = Portfolio(
            user_id=user_id,
            name=portfolio_data.name,
            description=portfolio_data.description
        )
        db.add(portfolio)
        db.commit()
        db.refresh(portfolio)
        return portfolio
    
    def get_user_portfolios(self, db: Session, user_id: int) -> List[Portfolio]:
        """Get all portfolios for a user"""
        return db.query(Portfolio).filter(
            Portfolio.user_id == user_id,
            Portfolio.is_active == True
        ).order_by(Portfolio.created_at.desc()).all()
    
    def get_portfolio(self, db: Session, portfolio_id: int, user_id: int) -> Optional[Portfolio]:
        """Get a specific portfolio for a user"""
        return db.query(Portfolio).filter(
            Portfolio.id == portfolio_id,
            Portfolio.user_id == user_id,
            Portfolio.is_active == True
        ).first()
    
    def update_portfolio(self, db: Session, portfolio_id: int, user_id: int, portfolio_data: Dict[str, Any]) -> Optional[Portfolio]:
        """Update a portfolio"""
        portfolio = self.get_portfolio(db, portfolio_id, user_id)
        if not portfolio:
            return None
        
        for key, value in portfolio_data.items():
            if hasattr(portfolio, key) and value is not None:
                setattr(portfolio, key, value)
        
        portfolio.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(portfolio)
        return portfolio
    
    def delete_portfolio(self, db: Session, portfolio_id: int, user_id: int) -> bool:
        """Soft delete a portfolio"""
        portfolio = self.get_portfolio(db, portfolio_id, user_id)
        if not portfolio:
            return False
        
        portfolio.is_active = False
        portfolio.updated_at = datetime.utcnow()
        db.commit()
        return True

class OptionLegService:
    def __init__(self):
        self.symbol_cache = {}  # Cache for symbol lookups
        self.price_cache = {}   # Cache for price lookups
        self.cache_ttl = 2     # Cache TTL in seconds
        self.last_cache_clear = time.time()
        # Database configuration from environment variables
        self.db_config = {
            'host': os.getenv("PGHOST", "localhost"),
            'port': os.getenv("PGPORT", "5432"),
            'dbname': os.getenv("PGDATABASE", "database_name"),
            'user': os.getenv("PGUSER", "username"),
            'password': os.getenv("PGPASSWORD", "password")
        }
    
    def clear_cache_if_needed(self):
        """Clear cache if TTL expired"""
        current_time = time.time()
        if current_time - self.last_cache_clear > self.cache_ttl:
            self.symbol_cache.clear()
            self.price_cache.clear()
            self.last_cache_clear = current_time
    
    def get_db_connection(self):
        """Get connection to the live prices database"""
        return psycopg2.connect(**self.db_config, cursor_factory=RealDictCursor)
    
    def create_option_leg(self, db: Session, portfolio_id: int, leg_data: OptionLegCreate) -> OptionLeg:
        """Create a new option leg in a portfolio"""
        leg = OptionLeg(
            portfolio_id=portfolio_id,
            index_name=leg_data.index_name,
            strike=leg_data.strike,
            option_type=leg_data.option_type,
            expiry=leg_data.expiry,
            action=leg_data.action,
            lots=leg_data.lots
        )
        db.add(leg)
        db.commit()
        db.refresh(leg)
        return leg
    
    def get_portfolio_legs(self, db: Session, portfolio_id: int) -> List[OptionLeg]:
        """Get all option legs for a portfolio"""
        return db.query(OptionLeg).filter(OptionLeg.portfolio_id == portfolio_id).all()
    
    def get_user_legs(self, db: Session, user_id: int) -> List[OptionLeg]:
        """Get all option legs for a user across all portfolios (for backward compatibility)"""
        return db.query(OptionLeg).join(Portfolio).filter(
            Portfolio.user_id == user_id,
            Portfolio.is_active == True
        ).all()
    
    def get_live_price(self, symbol: str) -> Optional[float]:
        """Get live price for a symbol from the database"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Query the live_prices table for the symbol
            cursor.execute("""
                SELECT price, timestamp, zerodha_price, zerodha_timestamp
                FROM live_prices 
                WHERE symbol = %s 
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (symbol,))
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result:
                # Prefer zerodha_price if available, otherwise use price
                return result['zerodha_price'] if result['zerodha_price'] is not None else result['price']
            return None
        except Exception as e:
            logger.error(f"Error getting live price for {symbol}: {e}")
            return None
    
    def find_symbol_by_details(self, db: Session, index_name: str, strike: float, option_type: str, expiry: date) -> Optional[str]:
        """Find the exact symbol for given option details"""
        try:
            # Get all symbols for this index
            all_symbols = self.get_available_options(db, index_name)
            
            # Filter by strike, option type, and expiry
            matching_symbols = [
                symbol for symbol in all_symbols
                if (symbol['strike'] == strike and 
                    symbol['option_type'] == option_type and 
                    symbol['expiry'] == expiry)
            ]
            
            return matching_symbols[0]['symbol'] if matching_symbols else None
            
        except Exception as e:
            return None
    
    def get_available_strikes(self, db: Session, index_name: str) -> List[float]:
        """Get all available strike prices for an index"""
        try:
            all_symbols = self.get_available_options(db, index_name)
            strikes = list(set(symbol['strike'] for symbol in all_symbols))
            return sorted(strikes)
        except Exception as e:
            return []
    
    def get_available_expiries(self, db: Session, index_name: str) -> List[date]:
        """Get all available expiry dates for an index"""
        try:
            all_symbols = self.get_available_options(db, index_name)
            expiries = list(set(symbol['expiry'] for symbol in all_symbols))
            return sorted(expiries)
        except Exception as e:
            return []
    
    def get_option_price(self, db: Session, symbol: str) -> Optional[float]:
        """Get current price for a specific option symbol"""
        try:
            # Check cache first
            if symbol in self.price_cache:
                return self.price_cache[symbol]
            
            # Query database
            price_record = db.query(LivePrice).filter(LivePrice.symbol == symbol).first()
            if price_record:
                # Prefer zerodha_price if available, otherwise use price
                current_price = price_record.zerodha_price if price_record.zerodha_price is not None else price_record.price
                if current_price is not None:
                    self.price_cache[symbol] = current_price
                    return current_price
            
            return None
            
        except Exception as e:
            return None
    
    def get_all_symbols(self, db: Session) -> List[Dict[str, Any]]:
        """Get all available option symbols from the database"""
        try:
            # Query the LivePrice table to get all available symbols
            price_records = db.query(LivePrice).filter(
                LivePrice.trade_symbol.isnot(None),
                LivePrice.strike_price.isnot(None),
                LivePrice.option_type.isnot(None),
                LivePrice.expiry_date.isnot(None)
            ).all()
            
            symbols = []
            for record in price_records:
                symbols.append({
                    'symbol': record.symbol,
                    'index_name': record.trade_symbol,
                    'strike': record.strike_price,
                    'option_type': record.option_type,
                    'expiry': record.expiry_date.date() if record.expiry_date else None
                })
            
            return symbols
        except Exception as e:
            logger.error(f"Error getting all symbols: {e}")
            return []
    
    def get_available_options(self, db: Session, index_name: str) -> List[Dict[str, Any]]:
        """Get all available options for an index with their details"""
        try:
            # Get all symbols for this index
            all_symbols = self.get_all_symbols(db)
            
            # Filter by index name
            index_symbols = [
                symbol for symbol in all_symbols
                if symbol['index_name'] == index_name
            ]
            
            return index_symbols
            
        except Exception as e:
            return []
    
    def get_legs_with_prices(self, db: Session, portfolio_id: int) -> List[Dict[str, Any]]:
        """Get portfolio legs with current prices and P&L calculations - OPTIMIZED with caching"""
        # Clear cache if needed
        self.clear_cache_if_needed()
        
        legs = self.get_portfolio_legs(db, portfolio_id)
        if not legs:
            return []
        
        # Collect all unique symbols we need to fetch prices for
        symbols_to_fetch = []
        leg_symbol_map = {}
        
        for leg in legs:
            symbol = self.find_symbol_by_details(db, leg.index_name, leg.strike, leg.option_type, leg.expiry)
            if symbol:
                symbols_to_fetch.append(symbol)
                leg_symbol_map[leg.id] = symbol
        
        # Fetch all prices in a single query
        prices = {}
        if symbols_to_fetch:
            # Check cache first
            uncached_symbols = [s for s in symbols_to_fetch if s not in self.price_cache]
            
            if uncached_symbols:
                price_records = db.query(LivePrice).filter(
                    LivePrice.symbol.in_(uncached_symbols)
                ).all()
                
                for record in price_records:
                    # Prefer zerodha_price if available, otherwise use price
                    current_price = record.zerodha_price if record.zerodha_price is not None else record.price
                    if current_price is not None:
                        self.price_cache[record.symbol] = current_price
            
            # Get prices from cache
            for symbol in symbols_to_fetch:
                if symbol in self.price_cache:
                    prices[symbol] = self.price_cache[symbol]
        
        # Build response with prices
        legs_with_prices = []
        for leg in legs:
            symbol = leg_symbol_map.get(leg.id)
            current_price = prices.get(symbol) if symbol else None
            current_value = self.calculate_pnl(leg, current_price) if current_price else 0.0
            
            leg_data = {
                'id': leg.id,
                'portfolio_id': leg.portfolio_id,
                'index_name': leg.index_name,
                'strike': leg.strike,
                'option_type': leg.option_type,
                'expiry': leg.expiry,
                'action': leg.action,
                'lots': leg.lots,
                'saved_at': leg.saved_at,
                'current_price': current_price,
                'current_value': current_value,  # This is now the current value, not P&L
                'symbol': symbol
            }
            legs_with_prices.append(leg_data)
        
        return legs_with_prices
    
    def calculate_pnl(self, leg: OptionLeg, current_price: float) -> float:
        """Calculate current value for a single option leg"""
        try:
            if current_price is None:
                return 0.0
            
            # Get lot size based on index
            lot_size = 75 if leg.index_name == 'NIFTY' else 20  # NIFTY: 75, SENSEX: 20
            
            # Calculate current value: current_price * lots * lot_size
            current_value = current_price * leg.lots * lot_size
            
            return round(current_value, 2)
        except Exception as e:
            return 0.0
    
    def calculate_net_premium(self, legs_with_prices: List[Dict[str, Any]]) -> float:
        """Calculate signed net premium (Sell = +, Buy = -)."""
        try:
            total_value = 0.0
            for leg in legs_with_prices:
                value = leg.get('current_value', 0.0) or 0.0
                action = (leg.get('action') or '').lower()
                sign = 1.0 if action == 'sell' else -1.0  # default Buy -> debit
                total_value += sign * value
            return round(total_value, 2)
        except Exception as e:
            return 0.0

    def calculate_total_pnl(self, legs_with_prices: List[Dict[str, Any]]) -> float:
        """Alias to net premium for the dashboard total."""
        return self.calculate_net_premium(legs_with_prices)

# Initialize services
portfolio_service = PortfolioService()
option_leg_service = OptionLegService() 