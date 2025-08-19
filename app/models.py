from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, date

# User models
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

# Portfolio models
class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

class PortfolioUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None

class PortfolioResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_active: bool
    option_legs_count: int = 0

    class Config:
        from_attributes = True

# Option leg models
class OptionLegCreate(BaseModel):
    portfolio_id: int
    index_name: str = Field(..., pattern=r"^(NIFTY|SENSEX)$")
    strike: float = Field(..., gt=0)
    option_type: str = Field(..., pattern=r"^(CE|PE)$")
    expiry: datetime
    action: str = Field(..., pattern=r"^(Buy|Sell)$")
    lots: int = Field(..., gt=0)

class OptionLegUpdate(BaseModel):
    index_name: Optional[str] = Field(None, pattern=r"^(NIFTY|SENSEX)$")
    strike: Optional[float] = Field(None, gt=0)
    option_type: Optional[str] = Field(None, pattern=r"^(CE|PE)$")
    expiry: Optional[datetime] = None
    action: Optional[str] = Field(None, pattern=r"^(Buy|Sell)$")
    lots: Optional[int] = Field(None, gt=0)

class OptionLegResponse(BaseModel):
    id: int
    portfolio_id: int
    index_name: str
    strike: float
    option_type: str
    expiry: datetime
    action: str
    lots: int
    saved_at: datetime
    current_price: Optional[float] = None
    current_value: Optional[float] = None

    class Config:
        from_attributes = True

class OptionLegBasicResponse(BaseModel):
    id: int
    portfolio_id: int
    index_name: str
    strike: float
    option_type: str
    expiry: datetime
    action: str
    lots: int
    saved_at: datetime

    class Config:
        from_attributes = True

# Strategy models (for backward compatibility)
class StrategyCreate(BaseModel):
    legs: List[OptionLegCreate]

class StrategyResponse(BaseModel):
    id: int
    user_id: int
    legs: List[OptionLegResponse]
    created_at: datetime

    class Config:
        from_attributes = True

# Live price models
class LivePriceResponse(BaseModel):
    symbol: str
    price: float
    timestamp: datetime

    class Config:
        from_attributes = True

class PriceUpdateResponse(BaseModel):
    portfolio_id: int
    legs: List[OptionLegResponse]
    net_premium: float
    total_pnl: float
    last_updated: datetime

# Market data models
class MarketDataResponse(BaseModel):
    index_name: str
    spot_price: Optional[float]
    available_strikes: List[float]
    available_expiries: List[str]
    timestamp: datetime 

# Market data models
class MarketDataResponse(BaseModel):
    index_name: str
    spot_price: Optional[float]
    available_strikes: List[float]
    available_expiries: List[str]
    timestamp: datetime

# Historical backtesting models
class HistoricalLegCreate(BaseModel):
    index_name: str = Field(..., pattern=r"^(NIFTY|SENSEX)$")
    strike: float = Field(..., gt=0)
    option_type: str = Field(..., pattern=r"^(CE|PE)$")
    expiry: date
    action: str = Field(..., pattern=r"^(Buy|Sell)$")
    lots: int = Field(..., gt=0)

class HistoricalBacktestCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    backtest_date: date
    legs: List[HistoricalLegCreate]

class HistoricalBacktestResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str]
    backtest_date: date
    legs: List[HistoricalLegCreate]
    created_at: datetime
    status: str  # 'running', 'completed', 'failed'
    total_legs: int
    net_premium_start: Optional[float] = None
    net_premium_end: Optional[float] = None

    class Config:
        from_attributes = True

class HistoricalBacktestResult(BaseModel):
    backtest_id: int
    datetime: datetime
    net_premium: float
    leg_values: Dict[str, float]  # leg_id -> value
    volume: Optional[int] = None

    class Config:
        from_attributes = True

class HistoricalExpiryResponse(BaseModel):
    index_name: str
    available_expiries: List[date]
    selected_date: date

class HistoricalDataPoint(BaseModel):
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

class HistoricalLegData(BaseModel):
    leg_id: str
    strike: float
    option_type: str
    expiry: date
    action: str
    lots: int
    data: List[HistoricalDataPoint]

class HistoricalBacktestSummary(BaseModel):
    backtest_id: int
    total_minutes: int
    net_premium_range: Dict[str, float]  # min, max
    net_premium_start: float
    net_premium_end: float
    total_pnl: float
    max_profit: float
    max_loss: float
    profitable_minutes: int
    loss_minutes: int
    win_rate: float

    class Config:
        from_attributes = True