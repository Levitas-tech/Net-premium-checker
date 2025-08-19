# Options Trading UI with Zerodha WebSocket Integration

A comprehensive web-based UI for creating and managing options trading legs (Buy/Sell) for NIFTY and SENSEX, using live market data from Zerodha's WebSocket, with local and AWS database persistence.

## 🏗️ System Architecture

### Backend (Python/FastAPI)
- **Authentication**: JWT-based with bcrypt password hashing
- **Database**: PostgreSQL for local storage, DynamoDB for AWS mirroring
- **WebSocket Integration**: Connects to existing Zerodha WebSocket (Kite_WebSocket.py)
- **API**: RESTful endpoints for option leg management and live price updates

### Frontend (React)
- **UI Framework**: React with Tailwind CSS
- **State Management**: React Query for server state, Context for auth
- **Real-time Updates**: 2-second polling for live price updates
- **Responsive Design**: Mobile-first approach

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- PostgreSQL
- AWS Account (optional, for DynamoDB)

### Backend Setup

1. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up PostgreSQL database**:
   ```sql
   CREATE DATABASE "Live_Trading";
   ```

3. **Configure environment variables** (create `.env` file):
   ```env
   DATABASE_URL=postgresql://postgres:kanishk@123@localhost:5432/Live_Trading
   SECRET_KEY=your-secret-key-here-change-in-production
   AWS_ACCESS_KEY_ID=your-aws-access-key
   AWS_SECRET_ACCESS_KEY=your-aws-secret-key
   AWS_REGION=us-east-1
   ```

4. **Start the backend server**:
   ```bash
   python main.py
   ```
   The API will be available at `http://localhost:8000`

### Frontend Setup

1. **Navigate to frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Start the development server**:
   ```bash
   npm start
   ```
   The UI will be available at `http://localhost:3000`

## 📊 Features

### Authentication
- User registration and login
- JWT token-based authentication
- Secure password hashing with bcrypt

### Option Leg Management
- Add multiple option legs (Buy/Sell)
- Support for NIFTY and SENSEX indices
- Configurable strike prices, expiry dates, and lots
- Real-time price updates every 2 seconds

### Live Trading Dashboard
- Real-time P&L calculations
- Net premium tracking (credit/debit)
- Live price updates with visual indicators
- Strategy saving and management

### Database Integration
- Local PostgreSQL storage for user data and option legs
- AWS DynamoDB mirroring for strategy persistence
- Live price data from Zerodha WebSocket

## 🔌 API Endpoints

### Authentication
- `POST /signup` - Register new user
- `POST /login` - Authenticate user
- `GET /me` - Get user profile

### Option Legs
- `POST /option-legs` - Create single option leg
- `GET /option-legs` - Get user's option legs
- `POST /save-strategy` - Save complete strategy

### Live Prices
- `GET /live-price/{symbol}` - Get live price for symbol
- `GET /all-prices-for-user` - Get all legs with updated prices

### Market Data
- `GET /available-strikes/{index_name}` - Get available strikes
- `GET /available-expiries/{index_name}` - Get available expiries

## 🗄️ Database Schema

### Local Database (PostgreSQL)
```sql
-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR UNIQUE NOT NULL,
    email VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Option legs table
CREATE TABLE option_legs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    index_name VARCHAR NOT NULL,
    strike DECIMAL NOT NULL,
    option_type VARCHAR NOT NULL,
    expiry TIMESTAMP NOT NULL,
    action VARCHAR NOT NULL,
    lots INTEGER NOT NULL,
    saved_at TIMESTAMP DEFAULT NOW()
);

-- Live prices table (from Zerodha WebSocket)
CREATE TABLE live_prices (
    id SERIAL PRIMARY KEY,
    instrument_token INTEGER,
    symbol VARCHAR,
    price DECIMAL,
    timestamp TIMESTAMP DEFAULT NOW()
);
```

### AWS DynamoDB
- Simplified schema for strategy mirroring
- No authentication logic in AWS
- Retry mechanism for failed writes

## 🎨 UI Components

### Authentication
- Login/Signup forms with validation
- Password visibility toggle
- Error handling and user feedback

### Dashboard
- Option leg cards with live data
- P&L summary with real-time updates
- Start/Stop tracking controls
- Add option leg modal

### Trading Interface
- Multi-leg strategy builder
- Live price panel with auto-refresh
- P&L calculations with visual indicators
- Indian currency formatting (INR)

## 🔧 Configuration

### Backend Configuration
- Database connections (PostgreSQL + DynamoDB)
- JWT settings and token expiration
- WebSocket update intervals
- CORS settings for frontend integration

### Frontend Configuration
- API base URL and proxy settings
- React Query caching and refetch intervals
- Tailwind CSS theme customization
- Currency and date formatting

## 🧪 Testing

### Backend Testing
```bash
# Run FastAPI tests
pytest app/tests/

# Test database connections
python -m pytest tests/test_database.py

# Test authentication
python -m pytest tests/test_auth.py
```

### Frontend Testing
```bash
cd frontend
npm test
```

## 🚀 Deployment

### Backend Deployment
1. Set up production PostgreSQL database
2. Configure AWS credentials for DynamoDB
3. Update environment variables
4. Deploy with uvicorn or gunicorn

### Frontend Deployment
1. Build production bundle:
   ```bash
   cd frontend
   npm run build
   ```
2. Deploy to static hosting (Netlify, Vercel, etc.)

## 📈 Performance Features

- **Real-time Updates**: 2-second polling for live prices
- **Optimistic UI**: Immediate feedback for user actions
- **Caching**: React Query for efficient data management
- **Error Handling**: Graceful degradation for network issues
- **Responsive Design**: Mobile-friendly interface

## 🔒 Security Features

- **JWT Authentication**: Secure token-based auth
- **Password Hashing**: bcrypt with salt
- **Input Validation**: Pydantic models for API validation
- **CORS Protection**: Configured for frontend integration
- **Rate Limiting**: API endpoint protection

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For issues and questions:
1. Check the existing issues
2. Create a new issue with detailed information
3. Include logs and error messages

## 🔄 Integration with Existing Zerodha WebSocket

The system integrates with your existing `Kite_WebSocket.py` by:
- Reading live prices from the `live_prices` table
- Using the same database connection parameters
- Maintaining compatibility with existing WebSocket data flow
- Adding user-specific option leg management on top

The WebSocket continues to run independently while the UI provides a user-friendly interface for managing option strategies. 