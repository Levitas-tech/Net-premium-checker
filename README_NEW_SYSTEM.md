# 🚀 Net Premium Checker - New System Setup Guide

## 📋 **Prerequisites Installation**

### **1. Install Python 3.8+**
- Download from: https://www.python.org/downloads/
- **IMPORTANT**: Check "Add Python to PATH" during installation
- Verify installation: `python --version`

### **2. Install Node.js 16+**
- Download from: https://nodejs.org/
- **IMPORTANT**: Check "Add to PATH" during installation
- Verify installation: `node --version` and `npm --version`

### **3. Install Git (Optional)**
- Download from: https://git-scm.com/
- Useful for future updates and version control

## 🔧 **Application Setup**

### **1. Extract/Copy Project**
```bash
# Extract your backup folder to C:\NetPremiumChecker
# OR clone from GitHub if you pushed it there
git clone https://github.com/yourusername/NetPremiumChecker.git
cd NetPremiumChecker
```

### **2. Setup Python Environment**
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
```

### **3. Setup Frontend**
```bash
cd frontend

# Install Node.js dependencies
npm install

# Go back to root directory
cd ..
```

## ⚙️ **Configuration Setup**

### **1. Environment Variables**
```bash
# Copy environment template
copy env.example .env

# Edit .env file with your settings
notepad .env
```

**Required .env settings:**
```env
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/net_premium_checker

# Historical Data Service Configuration
HISTORICAL_MYSQL_HOST=
HISTORICAL_MYSQL_PORT=3306
HISTORICAL_MYSQL_USER=admin
HISTORICAL_MYSQL_PASSWORD=
HISTORICAL_MYSQL_DATABASE=

# JWT Secret
SECRET_KEY=your_secret_key_here
```

### **2. Update Zerodha Credentials**
```bash
# Edit Kite_WebSocket.py
notepad Kite_WebSocket.py

# Update these lines with your credentials:
# Line ~319: password="your_new_password"
# Line ~318: user_id="your_user_id"
# Line ~317: api_key="your_api_key"
```

## 🔐 **Security Best Practices**

### **1. Protect Your .env File**
```bash
# NEVER commit .env to version control
# Add to .gitignore if using Git
echo ".env" >> .gitignore

# Set file permissions (Windows)
# Right-click .env → Properties → Security → Edit → Remove all users except your account
```

### **2. Secure Credentials Storage**
- **✅ DO**: Use environment variables in `.env` file
- **✅ DO**: Keep `.env` file in a secure location
- **✅ DO**: Use strong, unique passwords
- **✅ DO**: All hardcoded credentials have been removed from source code
- **❌ DON'T**: Hardcode credentials in source code
- **❌ DON'T**: Share `.env` file with others
- **❌ DON'T**: Commit credentials to version control

### **3. Environment Variables Required**
Your `.env` file must contain these variables for the application to work:

```env
# Database Configuration (PostgreSQL)
PGHOST=localhost
PGPORT=5432
PGDATABASE=your_database_name
PGUSER=your_username
PGPASSWORD=your_password

# Historical Data Service Configuration
HISTORICAL_MYSQL_HOST=
HISTORICAL_MYSQL_PORT=3306
HISTORICAL_MYSQL_USER=admin
HISTORICAL_MYSQL_PASSWORD=
HISTORICAL_MYSQL_DATABASE=

# JWT Secret
SECRET_KEY=your-secret-key-here-change-in-production

# Zerodha Configuration
ZERODHA_API_KEY=your-zerodha-api-key
ZERODHA_API_SECRET=your-zerodha-api-secret
```

### **4. Alternative: Windows Credential Manager**
For maximum security on Windows, you can store credentials in Windows Credential Manager:
```bash
# Install required package
pip install pywin32

# Then use the credential manager approach in your code
# (See the security examples in the code comments)
```

### **5. File Access Control**
```bash
# Restrict access to sensitive files
# Right-click on .env, Kite_WebSocket.py → Properties → Security
# Remove access for other users on the PC
# Only your user account should have access
```

## 🗄️ **Database Setup**

### **1. PostgreSQL (Audit Logs)**
```bash
# Install PostgreSQL if not already installed
# Download from: https://www.postgresql.org/download/windows/

# Create database
createdb net_premium_checker

# OR using psql:
psql -U postgres
CREATE DATABASE net_premium_checker;
\q
```

### **2. MySQL (Historical Data)**
- **No setup needed** - connects to existing AWS RDS instance
- Just ensure your .env file has correct credentials

## 🚀 **Starting the Application**

### **Method 1: Using start_all.py (Recommended)**
```bash
# Make sure you're in the root directory
cd C:\NetPremiumChecker

# Activate virtual environment
venv\Scripts\activate

# Start both backend and WebSocket
python start_all.py
```

### **Method 2: Manual Start (Alternative)**
```bash
# Terminal 1: Start Backend
venv\Scripts\activate
python main.py

# Terminal 2: Start Frontend
cd frontend
npm start

# Terminal 3: Start WebSocket (if needed separately)
venv\Scripts\activate
python Kite_WebSocket.py
```

## 🌐 **Access the Application**

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## ✅ **Verification Checklist**

- [ ] **Backend starts** at http://localhost:8000
- [ ] **Frontend loads** at http://localhost:3000
- [ ] **Database connections** work (check backend logs)
- [ ] **Historical backtesting** connects to MySQL
- [ ] **Zerodha WebSocket** connects successfully
- [ ] **All API endpoints** respond correctly
- [ ] **Cross-index backtesting** works as expected

## 🐛 **Troubleshooting**

### **Port Already in Use**
```bash
# Check what's using the ports
netstat -ano | findstr :8000
netstat -ano | findstr :3000

# Kill the process if needed
taskkill /PID <PID> /F
```

### **Python Not Found**
```bash
# Add Python to PATH manually
# System Properties → Environment Variables → Path → Add Python installation directory
# Usually: C:\Users\YourUsername\AppData\Local\Programs\Python\Python3x\
```

### **Database Connection Issues**
```bash
# Test PostgreSQL
psql -h localhost -U postgres -d net_premium_checker

# Test MySQL
mysql -h marketdatacollection.cngo8aiaa5xp.ap-south-1.rds.amazonaws.com -u admin -p
```

### **Frontend Build Issues**
```bash
cd frontend
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

## 📁 **File Structure**
```
NetPremiumChecker/
├── app/                    # Backend Python code
├── frontend/              # React frontend
├── venv/                  # Python virtual environment
├── .env                   # Environment variables
├── requirements.txt       # Python dependencies
├── package.json          # Node.js dependencies
├── main.py               # Backend entry point
├── start_all.py          # Unified startup script
└── Kite_WebSocket.py     # Zerodha WebSocket service
```

## 🔄 **Daily Usage**

### **Start the Application:**
```bash
cd C:\NetPremiumChecker
venv\Scripts\activate
python start_all.py
```

### **Stop the Application:**
- Press `Ctrl+C` in the terminal running `start_all.py`
- Or close the terminal windows

### **Update Dependencies:**
```bash
# Python packages
venv\Scripts\activate
pip install -r requirements.txt --upgrade

# Node.js packages
cd frontend
npm update
```

## 📞 **Support**

If you encounter issues:
1. Check the backend logs in the terminal
2. Check browser console for frontend errors
3. Verify all environment variables are set correctly
4. Ensure all prerequisites are installed and in PATH

## 🎯 **Quick Start Commands**

```bash
# One-time setup
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cd frontend && npm install && cd ..

# Daily usage
venv\Scripts\activate
python start_all.py
```

---

**Happy Trading! 🚀📈**
