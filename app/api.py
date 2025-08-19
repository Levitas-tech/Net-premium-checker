from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.database import get_db, User, OptionLeg, HistoricalBacktest, HistoricalBacktestLeg, HistoricalBacktestResult
from app.auth import (
    create_user, authenticate_user, create_access_token, 
    get_current_user, get_password_hash
)
from app.models import (
    UserCreate, UserLogin, Token, UserResponse, OptionLegCreate, 
    OptionLegResponse, StrategyCreate, StrategyResponse, 
    LivePriceResponse, PriceUpdateResponse, PortfolioCreate, PortfolioResponse, PortfolioUpdate, OptionLegUpdate, OptionLegBasicResponse,
    HistoricalBacktestCreate, HistoricalBacktestResponse, HistoricalExpiryResponse,
    HistoricalBacktestSummary, HistoricalLegCreate
)
from app.services import option_leg_service, portfolio_service
from app.audit import log_change, get_stats, fetch_recent
from app.historical_service import historical_backtest_service

import threading
import sys
import os

# Add the parent directory to sys.path to import Kite_WebSocket
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from Kite_WebSocket import start_websocket_service, stop_websocket_service, get_websocket_status
    WEBSOCKET_AVAILABLE = True
except ImportError as e:
    WEBSOCKET_AVAILABLE = False

app = FastAPI(
    title="Options Trading UI API",
    description="API for options trading with Zerodha WebSocket integration",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication endpoints
@app.post("/signup", response_model=UserResponse)
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    try:
        user = create_user(
            db=db,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password
        )
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@app.post("/login", response_model=Token)
def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return JWT token"""
    user = authenticate_user(db, user_credentials.username, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user

# Portfolio endpoints
@app.post("/portfolios", response_model=PortfolioResponse)
def create_portfolio(
    portfolio_data: PortfolioCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new portfolio"""
    try:
        portfolio = portfolio_service.create_portfolio(db, current_user.id, portfolio_data)
        try:
            log_change(
                action="create",
                entity="portfolio",
                entity_id=portfolio.id,
                user_id=current_user.id,
                username=current_user.username,
                portfolio_id=portfolio.id,
                details={"name": portfolio.name, "description": portfolio.description},
                portfolio_snapshot={
                    "name": portfolio.name,
                    "legs": [],
                },
            )
        except Exception:
            pass
        return portfolio
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create portfolio: {str(e)}"
        )

@app.get("/portfolios", response_model=List[PortfolioResponse])
def get_user_portfolios(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all portfolios for the current user"""
    try:
        portfolios = portfolio_service.get_user_portfolios(db, current_user.id)
        
        # Calculate leg count for each portfolio
        for portfolio in portfolios:
            portfolio.option_legs_count = len(portfolio.option_legs)
        
        return portfolios
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get portfolios: {str(e)}"
        )

@app.get("/portfolios/{portfolio_id}", response_model=PortfolioResponse)
def get_portfolio(
    portfolio_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific portfolio"""
    try:
        portfolio = portfolio_service.get_portfolio(db, portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found"
            )
        
        # Calculate leg count
        portfolio.option_legs_count = len(portfolio.option_legs)
        
        return portfolio
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get portfolio: {str(e)}"
        )

@app.put("/portfolios/{portfolio_id}", response_model=PortfolioResponse)
def update_portfolio(
    portfolio_id: int,
    portfolio_data: PortfolioUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a portfolio"""
    try:
        portfolio = portfolio_service.update_portfolio(db, portfolio_id, current_user.id, portfolio_data.dict(exclude_unset=True))
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found"
            )
        try:
            log_change(
                action="update",
                entity="portfolio",
                entity_id=portfolio.id,
                user_id=current_user.id,
                username=current_user.username,
                portfolio_id=portfolio.id,
                details=portfolio_data.dict(exclude_unset=True),
                portfolio_snapshot={
                    "name": portfolio.name,
                    "legs": [
                        {
                            "id": l.id,
                            "index_name": l.index_name,
                            "strike": l.strike,
                            "option_type": l.option_type,
                            "expiry": l.expiry,
                            "action": l.action,
                            "lots": l.lots,
                        } for l in portfolio.option_legs
                    ],
                },
            )
        except Exception:
            pass
        return portfolio
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update portfolio: {str(e)}"
        )

@app.delete("/portfolios/{portfolio_id}")
def delete_portfolio(
    portfolio_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a portfolio"""
    try:
        success = portfolio_service.delete_portfolio(db, portfolio_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found"
            )
        try:
            log_change(
                action="delete",
                entity="portfolio",
                entity_id=portfolio_id,
                user_id=current_user.id,
                username=current_user.username,
                portfolio_id=portfolio_id,
                details=None,
                portfolio_snapshot=None,
            )
        except Exception:
            pass
        return {"message": "Portfolio deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete portfolio: {str(e)}"
        )

# Option legs endpoints
@app.post("/portfolios/{portfolio_id}/option-legs", response_model=OptionLegBasicResponse)
def create_option_leg(
    portfolio_id: int,
    leg_data: OptionLegCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new option leg in a portfolio"""
    try:
        # Verify portfolio belongs to user
        portfolio = portfolio_service.get_portfolio(db, portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found"
            )
        
        leg = option_leg_service.create_option_leg(db, portfolio_id, leg_data)
        # Fire-and-forget audit log
        try:
            log_change(
                action="create",
                entity="option_leg",
                entity_id=leg.id,
                user_id=current_user.id,
                username=current_user.username,
                portfolio_id=portfolio_id,
                details={
                    "index_name": leg.index_name,
                    "strike": leg.strike,
                    "option_type": leg.option_type,
                    "expiry": leg.expiry.isoformat() if hasattr(leg.expiry, 'isoformat') else str(leg.expiry),
                    "action": leg.action,
                    "lots": leg.lots,
                },
                portfolio_snapshot={
                    "legs": [
                        {
                            "id": l.id,
                            "index_name": l.index_name,
                            "strike": l.strike,
                            "option_type": l.option_type,
                            "expiry": l.expiry,
                            "action": l.action,
                            "lots": l.lots,
                        } for l in portfolio.option_legs
                    ]
                }
            )
        except Exception:
            pass
        return leg
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create option leg: {str(e)}"
        )

@app.get("/portfolios/{portfolio_id}/option-legs", response_model=List[OptionLegBasicResponse])
def get_portfolio_option_legs(
    portfolio_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all option legs for a portfolio"""
    try:
        # Verify portfolio belongs to user
        portfolio = portfolio_service.get_portfolio(db, portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found"
            )
        
        legs = option_leg_service.get_portfolio_legs(db, portfolio_id)
        return legs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get option legs: {str(e)}"
        )

@app.put("/portfolios/{portfolio_id}/option-legs/{leg_id}", response_model=OptionLegBasicResponse)
def update_option_leg(
    portfolio_id: int,
    leg_id: int,
    leg_data: OptionLegUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an option leg in a portfolio"""
    try:
        # Verify portfolio belongs to user
        portfolio = portfolio_service.get_portfolio(db, portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found"
            )
        
        # Get the leg and verify it belongs to the portfolio
        leg = db.query(OptionLeg).filter(
            OptionLeg.id == leg_id,
            OptionLeg.portfolio_id == portfolio_id
        ).first()
        
        if not leg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Option leg not found"
            )
        
        # Update leg fields
        update_data = leg_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(leg, field):
                setattr(leg, field, value)
        
        db.commit()
        db.refresh(leg)
        try:
            log_change(
                action="update",
                entity="option_leg",
                entity_id=leg.id,
                user_id=current_user.id,
                username=current_user.username,
                portfolio_id=portfolio_id,
                details=update_data,
                portfolio_snapshot={
                    "legs": [
                        {
                            "id": l.id,
                            "index_name": l.index_name,
                            "strike": l.strike,
                            "option_type": l.option_type,
                            "expiry": l.expiry,
                            "action": l.action,
                            "lots": l.lots,
                        } for l in portfolio.option_legs
                    ]
                }
            )
        except Exception:
            pass
        return leg
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update option leg: {str(e)}"
        )

@app.delete("/portfolios/{portfolio_id}/option-legs/{leg_id}")
def delete_option_leg(
    portfolio_id: int,
    leg_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an option leg from a portfolio"""
    try:
        # Verify portfolio belongs to user
        portfolio = portfolio_service.get_portfolio(db, portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found"
            )
        
        # Get the leg and verify it belongs to the portfolio
        leg = db.query(OptionLeg).filter(
            OptionLeg.id == leg_id,
            OptionLeg.portfolio_id == portfolio_id
        ).first()
        
        if not leg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Option leg not found"
            )
        
        db.delete(leg)
        db.commit()
        try:
            log_change(
                action="delete",
                entity="option_leg",
                entity_id=leg_id,
                user_id=current_user.id,
                username=current_user.username,
                portfolio_id=portfolio_id,
                details=None,
                portfolio_snapshot={
                    "legs": [
                        {
                            "id": l.id,
                            "index_name": l.index_name,
                            "strike": l.strike,
                            "option_type": l.option_type,
                            "expiry": l.expiry,
                            "action": l.action,
                            "lots": l.lots,
                        } for l in portfolio.option_legs if l.id != leg_id
                    ]
                }
            )
        except Exception:
            pass
        
        return {"message": "Option leg deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete option leg: {str(e)}"
        )

# Backward compatibility endpoints
@app.post("/option-legs", response_model=OptionLegBasicResponse)
def create_option_leg_legacy(
    leg_data: OptionLegCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new option leg (legacy endpoint - requires portfolio_id)"""
    try:
        if not hasattr(leg_data, 'portfolio_id') or not leg_data.portfolio_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="portfolio_id is required"
            )
        
        # Verify portfolio belongs to user
        portfolio = portfolio_service.get_portfolio(db, leg_data.portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found"
            )
        
        leg = option_leg_service.create_option_leg(db, leg_data.portfolio_id, leg_data)
        return leg
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create option leg: {str(e)}"
        )

@app.get("/option-legs", response_model=List[OptionLegBasicResponse])
def get_user_option_legs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all option legs for the current user (legacy endpoint)"""
    try:
        legs = option_leg_service.get_user_legs(db, current_user.id)
        return legs
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get option legs: {str(e)}"
        )

@app.post("/save-strategy", response_model=StrategyResponse)
def save_strategy(
    strategy_data: StrategyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save a complete strategy with multiple legs"""
    try:
        legs = []
        for leg_data in strategy_data.legs:
            leg = option_leg_service.create_option_leg(db, current_user.id, leg_data)
            legs.append(leg)
        
        # Get legs with prices for calculations
        legs_with_prices = option_leg_service.get_legs_with_prices(db, current_user.id)
        net_premium = option_leg_service.calculate_net_premium(legs_with_prices)
        total_pnl = option_leg_service.calculate_total_pnl(legs_with_prices)
        
        return StrategyResponse(
            id=1,  # This would be a strategy ID in a real implementation
            user_id=current_user.id,
            legs=legs,
            net_premium=net_premium,
            total_pnl=total_pnl,
            last_updated=datetime.now()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save strategy: {str(e)}"
        )

# Live price endpoints
@app.get("/live-price/{symbol}", response_model=LivePriceResponse)
def get_live_price(symbol: str):
    """Get live price for a specific symbol"""
    price = option_leg_service.get_live_price(symbol)
    if price is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Price not found for symbol: {symbol}"
        )
    
    return LivePriceResponse(
        symbol=symbol,
        price=price,
        timestamp=datetime.now()
    )

@app.get("/portfolios/{portfolio_id}/prices", response_model=PriceUpdateResponse)
def get_portfolio_prices(
    portfolio_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all legs with updated prices and P&L for a specific portfolio"""
    try:
        # Verify portfolio belongs to user
        portfolio = portfolio_service.get_portfolio(db, portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found"
            )
        
        legs_with_prices = option_leg_service.get_legs_with_prices(db, portfolio_id)
        
        if not legs_with_prices:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No option legs found in portfolio"
            )
        
        net_premium = option_leg_service.calculate_net_premium(legs_with_prices)
        total_pnl = option_leg_service.calculate_total_pnl(legs_with_prices)
        
        return PriceUpdateResponse(
            portfolio_id=portfolio_id,
            legs=legs_with_prices,
            net_premium=net_premium,
            total_pnl=total_pnl,
            last_updated=datetime.now()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get prices: {str(e)}"
        )

# Backward compatibility endpoint
@app.get("/all-prices-for-user", response_model=PriceUpdateResponse)
def get_all_prices_for_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all legs with updated prices and P&L for the current user (legacy endpoint)"""
    try:
        # Get the first active portfolio for backward compatibility
        portfolios = portfolio_service.get_user_portfolios(db, current_user.id)
        if not portfolios:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No portfolios found for user"
            )
        
        portfolio_id = portfolios[0].id
        legs_with_prices = option_leg_service.get_legs_with_prices(db, portfolio_id)
        
        if not legs_with_prices:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No option legs found for user"
            )
        
        net_premium = option_leg_service.calculate_net_premium(legs_with_prices)
        total_pnl = option_leg_service.calculate_total_pnl(legs_with_prices)
        
        return PriceUpdateResponse(
            portfolio_id=portfolio_id,
            legs=legs_with_prices,
            net_premium=net_premium,
            total_pnl=total_pnl,
            last_updated=datetime.now()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get prices: {str(e)}"
        )

# Market data endpoints
@app.get("/available-strikes/{index_name}")
def get_available_strikes(index_name: str):
    """Get available strike prices for an index"""
    strikes = option_leg_service.get_available_strikes(index_name)
    return {"index_name": index_name, "strikes": strikes}

@app.get("/available-expiries/{index_name}")
def get_available_expiries(index_name: str):
    """Get available expiry dates for an index"""
    expiries = option_leg_service.get_available_expiries(index_name)
    return {"index_name": index_name, "expiries": expiries}

@app.get("/available-options/{index_name}")
def get_available_options(index_name: str):
    """Get all available options with prices for an index"""
    options = option_leg_service.get_available_options(index_name)
    return {"index_name": index_name, "options": options}

@app.get("/option-price/{index_name}")
def get_option_price(
    index_name: str, 
    strike: float, 
    option_type: str, 
    expiry: str
):
    """Get current price for a specific option"""
    try:
        # Accept flexible expiry formats: YYYY-MM-DD or full ISO datetime
        try:
            if len(expiry) == 10:  # 'YYYY-MM-DD'
                from datetime import date, time
                d = date.fromisoformat(expiry)
                expiry_date = datetime.combine(d, datetime.min.time())
            else:
                expiry_date = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
        except Exception:
            from datetime import date, time
            # Last resort: parse only the date part before 'T'
            parts = expiry.split('T')[0]
            d = date.fromisoformat(parts)
            expiry_date = datetime.combine(d, datetime.min.time())
        price = option_leg_service.get_option_price(index_name, strike, option_type, expiry_date)
        
        if price is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Price not found for {index_name} {strike} {option_type}"
            )
        
        return {
            "index_name": index_name,
            "strike": strike,
            "option_type": option_type,
            "expiry": expiry,
            "price": price,
            "timestamp": datetime.now()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting option price: {str(e)}"
        )

@app.get("/spot-price/{index_name}")
def get_spot_price(index_name: str):
    """Get current spot price for an index (NIFTY 50 or SENSEX)"""
    spot_symbol = "NIFTY 50" if index_name == "NIFTY" else "SENSEX"
    price = option_leg_service.get_live_price(spot_symbol)
    if price is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Spot price not found for {index_name}"
        )
    
    return {
        "index_name": index_name,
        "spot_symbol": spot_symbol,
        "price": price,
        "timestamp": datetime.now()
    }

@app.get("/market-data/{index_name}")
def get_market_data(index_name: str):
    """Get comprehensive market data for an index including spot price and available strikes/expiries"""
    try:
        # Get spot price
        spot_symbol = "NIFTY 50" if index_name == "NIFTY" else "SENSEX"
        spot_price = option_leg_service.get_live_price(spot_symbol)
        
        # Get available strikes and expiries
        strikes = option_leg_service.get_available_strikes(index_name)
        expiries = option_leg_service.get_available_expiries(index_name)
        
        return {
            "index_name": index_name,
            "spot_price": spot_price,
            "spot_symbol": spot_symbol,
            "available_strikes": strikes,
            "available_expiries": [exp.strftime('%Y-%m-%d') for exp in expiries],
            "timestamp": datetime.now()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get market data: {str(e)}"
        )

# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint"""
    audit = {}
    try:
        audit = get_stats()
    except Exception:
        audit = {"ok": False}
    return {"status": "healthy", "timestamp": datetime.now(), "audit": audit}

@app.get("/audit/recent")
def audit_recent(limit: int = 20):
    try:
        return {"rows": fetch_recent(limit)}
    except Exception as e:
        return {"rows": [], "error": str(e)}

# WebSocket control endpoints
@app.post("/websocket/start")
def start_websocket():
    """Start the global WebSocket service for all configured symbols"""
    if not WEBSOCKET_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WebSocket service not available"
        )
    
    # Check if WebSocket is already running
    status_info = get_websocket_status()
    if status_info.get('running', False):
        return {
            "status": "already_running",
            "message": "WebSocket service is already running",
            "trade_symbols": status_info.get('trade_symbols', ['NIFTY', 'SENSEX'])
        }
    
    try:
        success = start_websocket_service()
        if success:
            return {
                "status": "started",
                "message": "Global WebSocket service started for NIFTY and SENSEX",
                "trade_symbols": ["NIFTY", "SENSEX"]
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to start WebSocket service"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting WebSocket service: {str(e)}"
        )

@app.post("/websocket/stop")
def stop_websocket():
    """Stop the global WebSocket service"""
    if not WEBSOCKET_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WebSocket service not available"
        )
    
    try:
        stop_websocket_service()
        return {
            "status": "stopped",
            "message": "Global WebSocket service stopped"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error stopping WebSocket: {str(e)}"
        )

@app.get("/websocket/status")
def get_websocket_status_endpoint():
    """Get global WebSocket service status"""
    if not WEBSOCKET_AVAILABLE:
        return {
            "available": False,
            "message": "WebSocket service not available"
        }
    
    try:
        status_info = get_websocket_status()
        return {
            "available": True,
            **status_info
        }
    except Exception as e:
        return {
            "available": True,
            "error": str(e),
            "running": False
        }

@app.get("/websocket/status/public")
def get_websocket_status_public():
    """Get global WebSocket service status (public - no authentication required)"""
    if not WEBSOCKET_AVAILABLE:
        return {
            "available": False,
            "message": "WebSocket service not available"
        }
    
    try:
        status_info = get_websocket_status()
        return {
            "available": True,
            **status_info
        }
    except Exception as e:
        return {
            "available": True,
            "error": str(e),
            "running": False
        }

# Historical backtesting endpoints
@app.get("/historical/health")
def get_historical_service_health():
    """Check if the historical data service is available"""
    try:
        is_available = historical_backtest_service.is_available()
        return {
            "service": "historical_backtest",
            "status": "available" if is_available else "unavailable",
            "mysql_config": {
                "host": historical_backtest_service.mysql_config['host'],
                "port": historical_backtest_service.mysql_config['port'],
                "database": historical_backtest_service.mysql_config['database'],
                "user": historical_backtest_service.mysql_config['user']
            }
        }
    except Exception as e:
        return {
            "service": "historical_backtest",
            "status": "error",
            "error": str(e)
        }

@app.get("/historical/available-expiries/{index_name}")
def get_available_expiries(
    index_name: str, 
    selected_date: str,
    current_user: User = Depends(get_current_user)
):
    """Get available expiries for historical backtesting"""
    try:
        # Parse selected date
        selected_date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()
        
        # Validate index name
        if index_name not in ["NIFTY", "SENSEX"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Index name must be NIFTY or SENSEX"
            )
        
        expiries = historical_backtest_service.get_available_expiries(index_name, selected_date_obj)
        return expiries
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format. Use YYYY-MM-DD: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get available expiries: {str(e)}"
        )

@app.post("/historical/run-backtest", response_model=HistoricalBacktestResponse)
def run_historical_backtest(
    backtest_data: HistoricalBacktestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create and run a historical backtest"""
    try:
        # Create backtest
        backtest = historical_backtest_service.create_backtest(db, current_user.id, backtest_data)
        
        # Run backtest in background (you might want to use Celery or similar for production)
        try:
            success = historical_backtest_service.run_backtest(db, backtest.id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to run backtest"
                )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error running backtest: {str(e)}"
            )
        
        # Get updated backtest with results
        db.refresh(backtest)
        
        # Convert to response model
        legs = db.query(HistoricalBacktestLeg).filter(
            HistoricalBacktestLeg.backtest_id == backtest.id
        ).all()
        
        response_legs = []
        for leg in legs:
            response_leg = HistoricalLegCreate(
                index_name=leg.index_name,
                strike=leg.strike,
                option_type=leg.option_type,
                expiry=leg.expiry.date(),
                action=leg.action,
                lots=leg.lots
            )
            response_legs.append(response_leg)
        
        return HistoricalBacktestResponse(
            id=backtest.id,
            user_id=backtest.user_id,
            name=backtest.name,
            description=backtest.description,
            backtest_date=backtest.backtest_date,
            legs=response_legs,
            created_at=backtest.created_at,
            status=backtest.status,
            total_legs=len(response_legs),
            net_premium_start=backtest.net_premium_start,
            net_premium_end=backtest.net_premium_end
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create backtest: {str(e)}"
        )

@app.get("/historical/backtest/{backtest_id}/results")
def get_backtest_results(
    backtest_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get minute-wise results for a specific backtest"""
    try:
        # Verify backtest belongs to user
        backtest = db.query(HistoricalBacktest).filter(
            HistoricalBacktest.id == backtest_id,
            HistoricalBacktest.user_id == current_user.id
        ).first()
        
        if not backtest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backtest not found"
            )
        
        if backtest.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Backtest is not completed yet"
            )
        
        results = historical_backtest_service.get_backtest_results(db, backtest_id)
        return {"results": results}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get backtest results: {str(e)}"
        )

@app.get("/historical/backtest/{backtest_id}/summary")
def get_backtest_summary(
    backtest_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get summary statistics for a specific backtest"""
    try:
        # Verify backtest belongs to user
        backtest = db.query(HistoricalBacktest).filter(
            HistoricalBacktest.id == backtest_id,
            HistoricalBacktest.user_id == current_user.id
        ).first()
        
        if not backtest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backtest not found"
            )
        
        if backtest.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Backtest is not completed yet"
            )
        
        summary = historical_backtest_service.get_backtest_summary(db, backtest_id)
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get backtest summary: {str(e)}"
        )

@app.get("/historical/backtests", response_model=List[HistoricalBacktestResponse])
def get_user_backtests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all historical backtests for the current user"""
    try:
        backtests = historical_backtest_service.get_user_backtests(db, current_user.id)
        
        # Convert to response models
        response_backtests = []
        for backtest in backtests:
            legs = db.query(HistoricalBacktestLeg).filter(
                HistoricalBacktestLeg.backtest_id == backtest.id
            ).all()
            
            response_legs = []
            for leg in legs:
                response_leg = HistoricalLegCreate(
                    index_name=leg.index_name,
                    strike=leg.strike,
                    option_type=leg.option_type,
                    expiry=leg.expiry.date(),
                    action=leg.action,
                    lots=leg.lots
                )
                response_legs.append(response_leg)
            
            response_backtest = HistoricalBacktestResponse(
                id=backtest.id,
                user_id=backtest.user_id,
                name=backtest.name,
                description=backtest.description,
                backtest_date=backtest.backtest_date,
                legs=response_legs,
                created_at=backtest.created_at,
                status=backtest.status,
                total_legs=len(response_legs),
                net_premium_start=backtest.net_premium_start,
                net_premium_end=backtest.net_premium_end
            )
            response_backtests.append(response_backtest)
        
        return response_backtests
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get backtests: {str(e)}"
        )

@app.get("/historical/backtest/{backtest_id}/results")
def get_backtest_results(
    backtest_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get minute-wise results for a specific backtest"""
    try:
        # Verify backtest belongs to user
        backtest = db.query(HistoricalBacktest).filter(
            HistoricalBacktest.id == backtest_id,
            HistoricalBacktest.user_id == current_user.id
        ).first()
        
        if not backtest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backtest not found"
            )
        
        if backtest.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Backtest is not completed yet"
            )
        
        results = historical_backtest_service.get_backtest_results(db, backtest_id)
        return {"results": results}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get backtest results: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 