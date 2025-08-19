from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date
import pymysql
from pymysql.cursors import DictCursor
import json
import logging
import os
from app.database import HistoricalBacktest, HistoricalBacktestLeg, HistoricalBacktestResult, User
from app.models import (
    HistoricalBacktestCreate, HistoricalBacktestResponse, HistoricalBacktestResult as ResultModel,
    HistoricalExpiryResponse, HistoricalDataPoint, HistoricalLegData, HistoricalBacktestSummary
)
from app.config import settings
from app.audit import log_change

logger = logging.getLogger(__name__)

class HistoricalBacktestService:
    def __init__(self):
        # Make MySQL configuration configurable via environment variables
        self.mysql_config = {
            'host': os.getenv('HISTORICAL_MYSQL_HOST', 'marketdatacollection.cngo8aiaa5xp.ap-south-1.rds.amazonaws.com'),
            'port': int(os.getenv('HISTORICAL_MYSQL_PORT', '3306')),
            'user': os.getenv('HISTORICAL_MYSQL_USER', 'admin'),
            'password': os.getenv('HISTORICAL_MYSQL_PASSWORD', '140722!Levitas'),
            'database': os.getenv('HISTORICAL_MYSQL_DATABASE', 'SpotData'),
            'charset': 'utf8mb4',
            'cursorclass': DictCursor,
            'connect_timeout': 10,  # 10 second connection timeout
            'read_timeout': 30,      # 30 second read timeout
        }
        self.data_cache = {}  # Cache for historical data
        self.cache_ttl = 300  # 5 minutes cache TTL
        self._connection_available = None  # Cache connection status
    
    def is_available(self) -> bool:
        """Check if the historical data service is available"""
        if self._connection_available is None:
            try:
                # Try a simple connection test
                conn = self.get_mysql_connection()
                conn.close()
                self._connection_available = True
                logger.info("Historical data service is available")
            except Exception as e:
                logger.warning(f"Historical data service is not available: {e}")
                self._connection_available = False
        return self._connection_available
    
    def get_mysql_connection(self):
        """Get connection to MySQL historical data database"""
        try:
            return pymysql.connect(**self.mysql_config)
        except Exception as e:
            logger.error(f"Failed to connect to MySQL: {e}")
            raise
    
    def get_available_expiries(self, index_name: str, selected_date: date) -> HistoricalExpiryResponse:
        """Get 4 nearest available expiries for a given date and index"""
        if not self.is_available():
            # Return empty response if service is not available
            return HistoricalExpiryResponse(
                index_name=index_name,
                available_expiries=[],
                selected_date=selected_date
            )
        
        try:
            conn = self.get_mysql_connection()
            cursor = conn.cursor()
            
            # Get all available expiries for the index
            query = """
                SELECT DISTINCT 
                    SUBSTRING_INDEX(SUBSTRING_INDEX(table_name, '_', -2), '_', 1) as expiry_str
                FROM information_schema.tables 
                WHERE table_schema = %s
                AND table_name LIKE %s
                AND (table_name LIKE '%%_CALL' OR table_name LIKE '%%_PUT')
                ORDER BY expiry_str
            """
            
            pattern = f"{index_name}_%"
            cursor.execute(query, (self.mysql_config['database'], pattern))
            results = cursor.fetchall()
            
            # Parse expiry dates and filter by selected date
            available_expiries = []
            for result in results:
                try:
                    expiry_str = result['expiry_str']
                    # Parse date like "14Aug2025" - handle both formats
                    try:
                        # Try format like "14Aug2025"
                        expiry_date = datetime.strptime(expiry_str, "%d%b%Y").date()
                    except ValueError:
                        try:
                            # Try format like "14Aug25" (2-digit year)
                            expiry_date = datetime.strptime(expiry_str, "%d%b%y").date()
                        except ValueError:
                            # Try format like "14-Aug-2025"
                            expiry_date = datetime.strptime(expiry_str, "%d-%b-%Y").date()
                    
                    if expiry_date >= selected_date:
                        available_expiries.append(expiry_date)
                except ValueError as ve:
                    logger.warning(f"Could not parse expiry date '{expiry_str}': {ve}")
                    continue
            
            # Sort and take first 4
            available_expiries.sort()
            available_expiries = available_expiries[:4]
            
            cursor.close()
            conn.close()
            
            return HistoricalExpiryResponse(
                index_name=index_name,
                available_expiries=available_expiries,
                selected_date=selected_date
            )
            
        except Exception as e:
            logger.error(f"Error getting available expiries: {e}")
            # Return empty response on error
            return HistoricalExpiryResponse(
                index_name=index_name,
                available_expiries=[],
                selected_date=selected_date
            )
    
    def get_historical_data(self, index_name: str, strike: float, option_type: str, 
                           expiry: date, start_date: date, end_date: date) -> List[HistoricalDataPoint]:
        """Get historical minute-wise data for a specific option"""
        cache_key = f"{index_name}_{strike}_{option_type}_{expiry}_{start_date}_{end_date}"
        
        # Check cache first
        if cache_key in self.data_cache:
            cache_time, data = self.data_cache[cache_key]
            if (datetime.now() - cache_time).seconds < self.cache_ttl:
                return data
        
        try:
            conn = self.get_mysql_connection()
            cursor = conn.cursor()
            
            # Build table name - convert CE/PE to CALL/PUT
            expiry_str = expiry.strftime("%d%b%Y")
            option_suffix = "CALL" if option_type == "CE" else "PUT"
            table_name = f"{index_name}_{int(strike)}_{expiry_str}_{option_suffix}"
            
            logger.info(f"Looking for historical data table: {table_name}")
            
            # First check if the table exists
            check_table_query = """
                SELECT COUNT(*) as table_exists
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = %s
            """
            cursor.execute(check_table_query, (self.mysql_config['database'], table_name))
            table_exists = cursor.fetchone()['table_exists'] > 0
            
            if not table_exists:
                logger.error(f"Table {table_name} does not exist in database {self.mysql_config['database']}")
                # Try to find similar tables
                similar_tables_query = """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = %s 
                    AND table_name LIKE %s
                    ORDER BY table_name
                """
                pattern = f"{index_name}_{int(strike)}_{expiry_str}_%"
                cursor.execute(similar_tables_query, (self.mysql_config['database'], pattern))
                similar_tables = [row['table_name'] for row in cursor.fetchall()]
                logger.info(f"Similar tables found: {similar_tables}")
                raise Exception(f"Table {table_name} does not exist. Available similar tables: {similar_tables}")
            
            # Query historical data
            query = """
                SELECT datetime, open, high, low, close, volume
                FROM {}
                WHERE DATE(datetime) BETWEEN %s AND %s
                ORDER BY datetime
            """.format(table_name)
            
            cursor.execute(query, (start_date, end_date))
            results = cursor.fetchall()
            
            # Convert to HistoricalDataPoint objects
            data_points = []
            for result in results:
                data_point = HistoricalDataPoint(
                    datetime=result['datetime'],
                    open=float(result['open']),
                    high=float(result['high']),
                    low=float(result['low']),
                    close=float(result['close']),
                    volume=int(result['volume'])
                )
                data_points.append(data_point)
            
            cursor.close()
            conn.close()
            
            # Cache the data
            self.data_cache[cache_key] = (datetime.now(), data_points)
            
            return data_points
            
        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            raise
    
    def create_backtest(self, db: Session, user_id: int, backtest_data: HistoricalBacktestCreate) -> HistoricalBacktest:
        """Create a new historical backtest"""
        try:
            # Create backtest record
            backtest = HistoricalBacktest(
                user_id=user_id,
                name=backtest_data.name,
                description=backtest_data.description,
                backtest_date=backtest_data.backtest_date,
                status="running"
            )
            db.add(backtest)
            db.commit()
            db.refresh(backtest)
            
            # Create leg records
            for leg_data in backtest_data.legs:
                leg = HistoricalBacktestLeg(
                    backtest_id=backtest.id,
                    index_name=leg_data.index_name,
                    strike=leg_data.strike,
                    option_type=leg_data.option_type,
                    expiry=leg_data.expiry,
                    action=leg_data.action,
                    lots=leg_data.lots
                )
                db.add(leg)
            
            db.commit()
            
            return backtest
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating backtest: {e}")
            raise
    
    def run_backtest(self, db: Session, backtest_id: int) -> bool:
        """Execute the historical backtest and store results"""
        try:
            # Get backtest details
            backtest = db.query(HistoricalBacktest).filter(HistoricalBacktest.id == backtest_id).first()
            if not backtest:
                raise ValueError(f"Backtest {backtest_id} not found")
            
            legs = db.query(HistoricalBacktestLeg).filter(HistoricalBacktestLeg.backtest_id == backtest_id).all()
            if not legs:
                raise ValueError(f"No legs found for backtest {backtest_id}")
            
            # Get date range for backtest
            backtest_date = backtest.backtest_date
            start_date = backtest_date
            end_date = backtest_date
            
            # Get historical data for all legs
            leg_data_map = {}
            for leg in legs:
                data = self.get_historical_data(
                    leg.index_name, leg.strike, leg.option_type, 
                    leg.expiry, start_date, end_date
                )
                leg_data_map[leg.id] = data
            
            # Check if we have any data at all
            total_data_points = sum(len(data) for data in leg_data_map.values())
            if total_data_points == 0:
                # No data available for this date
                backtest.status = "failed"
                backtest.completed_at = datetime.utcnow()
                db.commit()
                
                error_msg = f"No market data available for date {backtest_date}"
                logger.warning(f"Backtest {backtest_id} failed: {error_msg}")
                raise ValueError(error_msg)
            
            # Find common time points across all legs
            all_timestamps = set()
            for leg_id, data in leg_data_map.items():
                for point in data:
                    all_timestamps.add(point.datetime)
            
            common_timestamps = sorted(list(all_timestamps))
            
            # Calculate net premium for each timestamp
            results = []
            for timestamp in common_timestamps:
                net_premium = 0.0
                leg_values = {}
                
                for leg in legs:
                    # Find data point for this timestamp
                    leg_data = next((p for p in leg_data_map[leg.id] if p.datetime == timestamp), None)
                    if leg_data:
                        # Calculate leg value
                        premium = leg_data.close
                        multiplier = leg.lots
                        
                        if leg.action == "Buy":
                            leg_value = -premium * multiplier  # Negative for buy
                        else:  # Sell
                            leg_value = premium * multiplier  # Positive for sell
                        
                        net_premium += leg_value
                        leg_values[str(leg.id)] = leg_value
                
                # Create result record
                result = HistoricalBacktestResult(
                    backtest_id=backtest_id,
                    datetime=timestamp,
                    net_premium=net_premium,
                    leg_values=json.dumps(leg_values),
                    volume=0  # Could be calculated from leg volumes if needed
                )
                results.append(result)
            
            # Store results in database
            for result in results:
                db.add(result)
            
            # Update backtest status and summary
            if results:
                backtest.net_premium_start = results[0].net_premium
                backtest.net_premium_end = results[-1].net_premium
                backtest.status = "completed"
                backtest.completed_at = datetime.utcnow()
            
            db.commit()
            
            # Log successful backtest completion
            try:
                # Get user details for audit log - use a fresh query to avoid session issues
                user = db.query(User).filter(User.id == backtest.user_id).first()
                if not user:
                    logger.warning(f"User not found for user_id: {backtest.user_id}")
                    username = "unknown"
                else:
                    username = user.username
                
                # Create portfolio snapshot with all legs
                portfolio_snapshot = {
                    "legs": [
                        {
                            "id": leg.id,
                            "lots": leg.lots,
                            "action": leg.action,
                            "expiry": leg.expiry.isoformat(),
                            "strike": leg.strike,
                            "index_name": leg.index_name,
                            "option_type": leg.option_type
                        } for leg in legs
                    ]
                }
                
                # Ensure we have valid data before logging
                if not backtest.id or not backtest.user_id:
                    logger.warning(f"Invalid backtest data for audit logging: id={backtest.id}, user_id={backtest.user_id}")
                    return True
                
                log_change(
                    action="complete",
                    entity="historical_backtest",
                    entity_id=backtest.id,
                    user_id=backtest.user_id,
                    username=username,
                    portfolio_id=None,
                    details={
                        "name": backtest.name,
                        "backtest_date": backtest.backtest_date.isoformat(),
                        "legs_count": len(legs),
                        "status": "completed",
                        "results_count": len(results),
                        "net_premium_start": results[0].net_premium if results else None,
                        "net_premium_end": results[-1].net_premium if results else None,
                        "completed_at": backtest.completed_at.isoformat() if backtest.completed_at else None
                    },
                    portfolio_snapshot=portfolio_snapshot
                )
                
            except Exception as e:
                logger.warning(f"Failed to log backtest completion: {e}")
                # Don't fail the backtest if audit logging fails
                pass
            
            logger.info(f"Backtest {backtest_id} completed with {len(results)} data points")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error running backtest: {e}")
            
            # Update backtest status to failed
            try:
                backtest = db.query(HistoricalBacktest).filter(HistoricalBacktest.id == backtest_id).first()
                if backtest:
                    backtest.status = "failed"
                    db.commit()
            except:
                pass
            
            raise
    
    def get_backtest_results(self, db: Session, backtest_id: int) -> List[ResultModel]:
        """Get minute-wise results for a completed backtest"""
        try:
            results = db.query(HistoricalBacktestResult).filter(
                HistoricalBacktestResult.backtest_id == backtest_id
            ).order_by(HistoricalBacktestResult.datetime).all()
            
            # Convert to response models
            response_results = []
            for result in results:
                leg_values = json.loads(result.leg_values) if result.leg_values else {}
                
                response_result = ResultModel(
                    backtest_id=result.backtest_id,
                    datetime=result.datetime,
                    net_premium=result.net_premium,
                    leg_values=leg_values,
                    volume=result.volume
                )
                response_results.append(response_result)
            
            return response_results
            
        except Exception as e:
            logger.error(f"Error getting backtest results: {e}")
            raise
    
    def get_backtest_summary(self, db: Session, backtest_id: int) -> HistoricalBacktestSummary:
        """Get summary statistics for a completed backtest"""
        try:
            results = self.get_backtest_results(db, backtest_id)
            if not results:
                raise ValueError("No results found for backtest")
            
            # Calculate summary statistics
            net_premiums = [r.net_premium for r in results]
            net_premium_start = results[0].net_premium
            net_premium_end = results[-1].net_premium
            
            total_pnl = net_premium_end - net_premium_start
            max_profit = max(net_premiums)
            max_loss = min(net_premiums)
            
            profitable_minutes = sum(1 for p in net_premiums if p > 0)
            loss_minutes = sum(1 for p in net_premiums if p < 0)
            total_minutes = len(results)
            win_rate = (profitable_minutes / total_minutes) * 100 if total_minutes > 0 else 0
            
            return HistoricalBacktestSummary(
                backtest_id=backtest_id,
                total_minutes=total_minutes,
                net_premium_range={"min": max_loss, "max": max_profit},
                net_premium_start=net_premium_start,
                net_premium_end=net_premium_end,
                total_pnl=total_pnl,
                max_profit=max_profit,
                max_loss=max_loss,
                profitable_minutes=profitable_minutes,
                loss_minutes=loss_minutes,
                win_rate=win_rate
            )
            
        except Exception as e:
            logger.error(f"Error getting backtest summary: {e}")
            raise
    
    def get_user_backtests(self, db: Session, user_id: int) -> List[HistoricalBacktest]:
        """Get all backtests for a user"""
        try:
            return db.query(HistoricalBacktest).filter(
                HistoricalBacktest.user_id == user_id
            ).order_by(HistoricalBacktest.created_at.desc()).all()
        except Exception as e:
            logger.error(f"Error getting user backtests: {e}")
            raise

# Initialize service
historical_backtest_service = HistoricalBacktestService()