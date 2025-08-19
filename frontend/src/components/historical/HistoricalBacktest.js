import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import axios from 'axios';
import { Calendar, Play, BarChart3, Download, AlertCircle, CheckCircle, XCircle, X } from 'lucide-react';
import * as XLSX from 'xlsx';

const HistoricalBacktest = () => {
  const [selectedDate, setSelectedDate] = useState('');
  const [availableExpiries, setAvailableExpiries] = useState({}); // Changed to object to store expiries per index
  const [legs, setLegs] = useState([]);
  const [backtestName, setBacktestName] = useState('');
  const [backtestDescription, setBacktestDescription] = useState('');
  const [connectionStatus, setConnectionStatus] = useState('checking'); // checking, connected, failed
  const [selectedBacktest, setSelectedBacktest] = useState(null);
  const [showResults, setShowResults] = useState(false);
  const [showSummary, setShowSummary] = useState(false);
  const [showAllResults, setShowAllResults] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  
  const queryClient = useQueryClient();

  // Check backend connection status
  useEffect(() => {
    const checkConnection = async () => {
      try {
        const response = await axios.get('/historical/health');
        if (response.data.status === 'available') {
          setConnectionStatus('connected');
        } else {
          setConnectionStatus('failed');
        }
      } catch (error) {
        setConnectionStatus('failed');
      }
    };
    
    checkConnection();
  }, []);

  // Get available expiries when date changes or when legs change
  useEffect(() => {
    if (!selectedDate || connectionStatus !== 'connected') return;
    
    const fetchExpiries = async () => {
      const expiriesMap = {};
      
      try {
        // Fetch expiries for both NIFTY and SENSEX
        const [niftyResponse, sensexResponse] = await Promise.all([
          axios.get(`/historical/available-expiries/NIFTY?selected_date=${selectedDate}`),
          axios.get(`/historical/available-expiries/SENSEX?selected_date=${selectedDate}`)
        ]);
        
        expiriesMap.NIFTY = niftyResponse.data.available_expiries || [];
        expiriesMap.SENSEX = sensexResponse.data.available_expiries || [];
        
        setAvailableExpiries(expiriesMap);
      } catch (error) {
        console.error('Error fetching expiries:', error);
        setAvailableExpiries({});
      }
    };
    
    fetchExpiries();
  }, [selectedDate, connectionStatus]);

  // Get user's backtests
  const { data: backtests, isLoading: loadingBacktests, error: backtestsError } = useQuery(
    'historical-backtests',
    () => axios.get('/historical/backtests'),
    {
      enabled: connectionStatus === 'connected',
      onError: (error) => {
        // Silent error handling - user will see empty backtest list
      }
    }
  );

  // Run backtest mutation
  const runBacktestMutation = useMutation(
    (backtestData) => axios.post('/historical/run-backtest', backtestData),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('historical-backtests');
        setSuccessMessage('Backtest started successfully!');
        setErrorMessage(''); // Clear any previous errors
        // Auto-hide success message after 5 seconds
        setTimeout(() => setSuccessMessage(''), 5000);
      },
      onError: (error) => {
        // Extract detailed error message from backend
        let errorMessage = 'Unknown error occurred';
        
        if (error.response?.data?.detail) {
          errorMessage = error.response.data.detail;
        } else if (error.response?.data?.message) {
          errorMessage = error.response.data.message;
        } else if (error.message) {
          errorMessage = error.message;
        }
        
        // Show more user-friendly error message
        if (errorMessage.includes('No market data available')) {
          errorMessage = `No market data available for the selected date. This usually means the market was closed (weekend/holiday) or data is not available for that date.`;
        }
        
        setErrorMessage(`Backtest Failed: ${errorMessage}`);
        setSuccessMessage(''); // Clear any previous success messages
        // Auto-hide error message after 10 seconds
        setTimeout(() => setErrorMessage(''), 10000);
      }
    }
  );

  // Get backtest results
  const { data: backtestResults, isLoading: loadingResults } = useQuery(
    ['backtest-results', selectedBacktest?.id],
    () => axios.get(`/historical/backtest/${selectedBacktest.id}/results`),
    {
      enabled: !!selectedBacktest && showResults,
      onError: (error) => {
        setErrorMessage('Failed to load backtest results');
        setTimeout(() => setErrorMessage(''), 5000);
      }
    }
  );

  // Get backtest summary
  const { data: backtestSummary, isLoading: loadingSummary } = useQuery(
    ['backtest-summary', selectedBacktest?.id],
    () => axios.get(`/historical/backtest/${selectedBacktest.id}/summary`),
    {
      enabled: !!selectedBacktest && showSummary,
      onError: (error) => {
        setErrorMessage('Failed to load backtest summary');
        setTimeout(() => setErrorMessage(''), 5000);
      }
    }
  );

  // Download results as Excel
  const downloadExcel = () => {
    if (!backtestResults?.data?.results) return;
    
    // Create worksheet data - HARDCODED to exactly 2 columns
    const headers = ['DateTime', 'Net Premium'];
    
    // Process each result to ensure correct mapping
    const worksheetData = backtestResults.data.results.map((result, index) => {
      // Column 1: DateTime - combine date and time from ISO format
      let dateTime = 'N/A';
      if (result.datetime) {
        try {
          const dt = new Date(result.datetime);
          if (!isNaN(dt.getTime())) {
            // Force Indian format: DD-MM-YYYY, HH:MM:SS am/pm
            const day = dt.getDate().toString().padStart(2, '0');
            const month = (dt.getMonth() + 1).toString().padStart(2, '0');
            const year = dt.getFullYear();
            const hours = dt.getHours();
            const minutes = dt.getMinutes().toString().padStart(2, '0');
            const seconds = dt.getSeconds().toString().padStart(2, '0');
            const ampm = hours >= 12 ? 'pm' : 'am';
            const displayHours = (hours % 12 || 12).toString().padStart(2, '0');
            
            dateTime = `${day}-${month}-${year}, ${displayHours}:${minutes}:${seconds} ${ampm}`;
          } else {
            dateTime = result.datetime;
          }
        } catch (e) {
          dateTime = result.datetime;
        }
      }
      
      // Column 2: Net Premium - ensure it's a number
      let netPremium = 'N/A';
      if (result.net_premium !== undefined && typeof result.net_premium === 'number') {
        netPremium = result.net_premium.toFixed(2);
      }
      
      // Return exactly 2 columns as array
      return [dateTime, netPremium];
    });
    
    // Combine headers and data
    const allData = [headers, ...worksheetData];
    
    // Convert to XLSX format and download
    try {
      // Create workbook and worksheet using xlsx library
      const worksheet = XLSX.utils.aoa_to_sheet(allData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Backtest Results');
      
      // Generate XLSX buffer and download
      const xlsxBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' });
      
      // Create and download file
      const blob = new Blob([xlsxBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', `backtest_${selectedBacktest.id}_results.xlsx`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (error) {
      // Fallback to CSV if XLSX fails
      setErrorMessage('XLSX generation failed. Falling back to CSV format.');
      setTimeout(() => setErrorMessage(''), 5000);
      downloadAsCSV();
    }
  };
  
  // Fallback CSV function
  const downloadAsCSV = () => {
    if (!backtestResults?.data?.results) return;
    
    const headers = ['DateTime', 'Net Premium'];
    const csvRows = backtestResults.data.results.map((result, index) => {
      let dateTime = 'N/A';
      if (result.datetime) {
        try {
          const dt = new Date(result.datetime);
          if (!isNaN(dt.getTime())) {
            const day = dt.getDate().toString().padStart(2, '0');
            const month = (dt.getMonth() + 1).toString().padStart(2, '0');
            const year = dt.getFullYear();
            const hours = dt.getHours();
            const minutes = dt.getMinutes().toString().padStart(2, '0');
            const seconds = dt.getSeconds().toString().padStart(2, '0');
            const ampm = hours >= 12 ? 'pm' : 'am';
            const displayHours = (hours % 12 || 12).toString().padStart(2, '0');
            
            dateTime = `${day}-${month}-${year}, ${displayHours}:${minutes}:${seconds} ${ampm}`;
          } else {
            dateTime = result.datetime;
          }
        } catch (e) {
          dateTime = result.datetime;
        }
      }
      
      let netPremium = 'N/A';
      if (result.net_premium !== undefined && typeof result.net_premium === 'number') {
        netPremium = result.net_premium.toFixed(2);
      }
      
      return `${dateTime},${netPremium}`;
    });
    
    const csvContent = [headers.join(','), ...csvRows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `backtest_${selectedBacktest.id}_results.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Add a new leg
  const addLeg = () => {
    const newLeg = {
      id: Date.now(),
      index_name: 'NIFTY', // Default to NIFTY
      strike: '',
      option_type: 'CE',
      expiry: '',
      action: 'Buy',
      lots: 1
    };
    setLegs([...legs, newLeg]);
  };

  // Remove a leg
  const removeLeg = (legId) => {
    setLegs(legs.filter(leg => leg.id !== legId));
  };

  // Update leg field
  const updateLeg = (legId, field, value) => {
    setLegs(legs.map(leg => {
      if (leg.id === legId) {
        const updatedLeg = { ...leg, [field]: value };
        
        // If index changes, reset expiry since different indexes have different expiries
        if (field === 'index_name') {
          updatedLeg.expiry = '';
        }
        
        return updatedLeg;
      }
      return leg;
    }));
  };

  // Run the backtest
  const runBacktest = () => {
    if (!backtestName.trim()) {
      setErrorMessage('Please enter a backtest name');
      setTimeout(() => setErrorMessage(''), 5000);
      return;
    }
    if (legs.length === 0) {
      setErrorMessage('Please add at least one leg');
      setTimeout(() => setErrorMessage(''), 5000);
      return;
    }

    const backtestData = {
      name: backtestName,
      description: backtestDescription,
      backtest_date: selectedDate,
      legs: legs.map(leg => ({
        index_name: leg.index_name,
        strike: parseFloat(leg.strike),
        option_type: leg.option_type,
        expiry: leg.expiry,
        action: leg.action,
        lots: parseInt(leg.lots)
      }))
    };

    runBacktestMutation.mutate(backtestData);
  };

  // Format date for display
  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-IN');
  };

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center">
          <BarChart3 className="mr-2" />
          Historical Backtesting
        </h2>

        {/* Connection Status */}
        {connectionStatus === 'checking' && (
          <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-center space-x-2">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
              <span className="text-sm font-medium text-blue-800">Checking connection to historical data service...</span>
            </div>
          </div>
        )}

        {connectionStatus === 'failed' && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center space-x-2">
              <XCircle className="h-5 w-5 text-red-500" />
              <span className="text-sm font-medium text-red-800">Connection Failed</span>
            </div>
            <p className="text-sm text-red-700 mt-1">
              Unable to connect to the historical data service. This could be due to:
            </p>
            <ul className="text-sm text-red-700 mt-2 list-disc list-inside">
              <li>MySQL database connection issues</li>
              <li>Historical service not running</li>
              <li>Network connectivity problems</li>
            </ul>
            <p className="text-sm text-red-700 mt-2">
              Please check your backend logs or contact support.
            </p>
          </div>
        )}

        {connectionStatus === 'connected' && (
          <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
            <div className="flex items-center space-x-2">
              <CheckCircle className="h-5 w-5 text-green-500" />
              <span className="text-sm font-medium text-green-800">Connected to Historical Data Service</span>
            </div>
          </div>
        )}
        
        {/* Error and Success Messages */}
        {errorMessage && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-start">
              <XCircle className="h-5 w-5 text-red-600 mt-0.5 mr-3 flex-shrink-0" />
              <div className="flex-1">
                <h4 className="font-medium text-red-800 mb-1">Backtest Error</h4>
                <p className="text-red-700 text-sm">{errorMessage}</p>
              </div>
              <button
                onClick={() => setErrorMessage('')}
                className="text-red-400 hover:text-red-600"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
        
        {successMessage && (
          <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
            <div className="flex items-start">
              <CheckCircle className="h-5 w-5 text-green-600 mt-0.5 mr-3 flex-shrink-0" />
              <div className="flex-1">
                <h4 className="font-medium text-green-800 mb-1">Success</h4>
                <p className="text-green-700 text-sm">{successMessage}</p>
              </div>
              <button
                onClick={() => setSuccessMessage('')}
                className="text-green-400 hover:text-green-600"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {/* Only show content if connected */}
        {connectionStatus === 'connected' ? (
          <>
            {/* Configuration Section */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Backtest Date
                </label>
                <input
                  type="date"
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Available Expiries
                </label>
                <div className="text-sm text-gray-600">
                  {Object.keys(availableExpiries).length > 0 ? (
                    <div className="space-y-1">
                      {Object.entries(availableExpiries).map(([index, expiries]) => (
                        <div key={index} className="flex items-center space-x-2">
                          <span className="font-medium text-gray-700">{index}:</span>
                          <span className="text-gray-600">
                            {expiries.length > 0 ? expiries.map(exp => formatDate(exp)).join(', ') : 'No expiries available'}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    'Select date first'
                  )}
                </div>
              </div>
            </div>

            {/* Cross-Index Information */}
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-start">
                <BarChart3 className="h-5 w-5 text-blue-600 mt-0.5 mr-3 flex-shrink-0" />
                <div>
                  <h4 className="font-medium text-blue-800 mb-1">Cross-Index Backtesting</h4>
                  <p className="text-blue-700 text-sm">
                    You can now combine NIFTY and SENSEX legs in the same backtest! Each leg can have its own index selection, 
                    allowing you to create sophisticated multi-index strategies. Simply select the desired index for each individual leg below.
                  </p>
                </div>
              </div>
            </div>

            {/* Backtest Details */}
            <div className="mb-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Backtest Name
                  </label>
                  <input
                    type="text"
                    value={backtestName}
                    onChange={(e) => setBacktestName(e.target.value)}
                    placeholder="Enter backtest name"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Description (Optional)
                  </label>
                  <input
                    type="text"
                    value={backtestDescription}
                    onChange={(e) => setBacktestDescription(e.target.value)}
                    placeholder="Enter description"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
            </div>

            {/* Legs Configuration */}
            <div className="mb-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold text-gray-900">Option Legs</h3>
                <button
                  onClick={addLeg}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  Add Leg
                </button>
              </div>

              {legs.length === 0 && (
                <div className="text-center py-8 text-gray-500 border-2 border-dashed border-gray-300 rounded-lg">
                  <BarChart3 className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                  <p>No option legs added yet.</p>
                  <p className="text-sm">Click "Add Leg" to start building your strategy.</p>
                </div>
              )}

              {legs.map((leg, index) => (
                <div key={leg.id} className="border border-gray-200 rounded-lg p-4 mb-4">
                  <div className="grid grid-cols-2 md:grid-cols-7 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Index</label>
                      <select
                        value={leg.index_name}
                        onChange={(e) => updateLeg(leg.id, 'index_name', e.target.value)}
                        className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                      >
                        <option value="NIFTY">NIFTY</option>
                        <option value="SENSEX">SENSEX</option>
                      </select>
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Strike</label>
                      <input
                        type="number"
                        value={leg.strike}
                        onChange={(e) => updateLeg(leg.id, 'strike', e.target.value)}
                        placeholder="Strike"
                        className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
                      <select
                        value={leg.option_type}
                        onChange={(e) => updateLeg(leg.id, 'option_type', e.target.value)}
                        className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                      >
                        <option value="CE">CE</option>
                        <option value="PE">PE</option>
                      </select>
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Expiry</label>
                      <select
                        value={leg.expiry}
                        onChange={(e) => updateLeg(leg.id, 'expiry', e.target.value)}
                        className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                      >
                        <option value="">Select expiry</option>
                        {availableExpiries[leg.index_name]?.map(exp => (
                          <option key={exp} value={exp}>
                            {formatDate(exp)}
                          </option>
                        ))}
                      </select>
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Action</label>
                      <select
                        value={leg.action}
                        onChange={(e) => updateLeg(leg.id, 'action', e.target.value)}
                        className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                      >
                        <option value="Buy">Buy</option>
                        <option value="Sell">Sell</option>
                      </select>
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Lots</label>
                      <input
                        type="number"
                        value={leg.lots}
                        onChange={(e) => updateLeg(leg.id, 'lots', e.target.value)}
                        min="1"
                        className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                      />
                    </div>
                    
                    <div className="flex items-end">
                      <button
                        onClick={() => removeLeg(leg.id)}
                        className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Run Backtest Button */}
            <div className="mb-8">
              <button
                onClick={runBacktest}
                disabled={runBacktestMutation.isLoading || legs.length === 0}
                className="w-full md:w-auto px-6 py-3 bg-green-600 text-white rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
              >
                <Play className="mr-2" />
                {runBacktestMutation.isLoading ? 'Running...' : 'Run Backtest'}
              </button>
            </div>

            {/* Previous Backtests */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Previous Backtests</h3>
              
              {loadingBacktests ? (
                <div className="text-center py-4">Loading...</div>
              ) : backtestsError ? (
                <div className="text-center py-4 text-red-600">
                  <AlertCircle className="mx-auto h-8 w-8 mb-2" />
                  Error loading backtests. Please try again.
                </div>
              ) : backtests?.data?.length > 0 ? (
                <div className="space-y-4">
                  {backtests.data.map((backtest) => (
                    <div key={backtest.id} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex justify-between items-start">
                        <div>
                          <h4 className="font-semibold text-gray-900">{backtest.name}</h4>
                          <p className="text-sm text-gray-600">{backtest.description}</p>
                          <div className="text-sm text-gray-500 mt-1">
                            Date: {formatDate(backtest.backtest_date)} | 
                            Status: <span className={`font-medium ${
                              backtest.status === 'completed' ? 'text-green-600' : 
                              backtest.status === 'failed' ? 'text-red-600' : 'text-yellow-600'
                            }`}>{backtest.status}</span> | 
                            Legs: {backtest.total_legs}
                          </div>
                        </div>
                        
                        <div className="flex space-x-2">
                          {backtest.status === 'completed' && (
                            <>
                              <button
                                onClick={() => {
                                  setSelectedBacktest(backtest);
                                  setShowResults(true);
                                  setShowSummary(false);
                                  setShowAllResults(false);
                                }}
                                className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
                              >
                                View Results
                              </button>
                              <button
                                onClick={() => {
                                  setSelectedBacktest(backtest);
                                  setShowSummary(true);
                                  setShowResults(false);
                                  setShowAllResults(false);
                                }}
                                className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700"
                              >
                                Summary
                              </button>
                            </>
                          )}
                          {backtest.status === 'failed' && (
                            <button
                              onClick={() => {
                                setSelectedBacktest(backtest);
                                setShowResults(false);
                                setShowSummary(false);
                                setShowAllResults(false);
                              }}
                              className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700"
                            >
                              View Error
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  No backtests found. Create your first backtest above.
                </div>
              )}
            </div>

            {/* Results and Summary Display */}
            {loadingResults && showResults && selectedBacktest && (
              <div className="mt-8 p-6 bg-white rounded-lg shadow-lg">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-xl font-bold text-gray-900">Backtest Results</h3>
                  <div className="flex space-x-2">
                    <button
                      onClick={downloadExcel}
                      className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700"
                      title="Download all results as Excel file (DateTime + Net Premium only)"
                    >
                      <Download className="mr-1" /> Download Excel
                    </button>
                    <button
                      onClick={() => {
                        setShowResults(false);
                        setSelectedBacktest(null);
                      }}
                      className="text-gray-500 hover:text-gray-700"
                    >
                      <X className="h-5 w-5" />
                    </button>
                  </div>
                </div>
                <p className="text-sm text-gray-600">Loading results for backtest ID: {selectedBacktest.id}...</p>
              </div>
            )}
            
            {/* Results Display */}
            {backtestResults && showResults && selectedBacktest && (
              <div className="mt-8 p-6 bg-white rounded-lg shadow-lg">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-xl font-bold text-gray-900">Backtest Results</h3>
                  <div className="flex space-x-2">
                    <button
                      onClick={downloadExcel}
                      className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700"
                      title="Download all results as Excel file (DateTime + Net Premium only)"
                    >
                      <Download className="mr-1" /> Download Excel
                    </button>
                    <button
                      onClick={() => {
                        setShowResults(false);
                        setSelectedBacktest(null);
                      }}
                      className="text-gray-500 hover:text-gray-700"
                    >
                      <X className="h-5 w-5" />
                    </button>
                  </div>
                </div>
                <div className="mb-4">
                  <h4 className="font-semibold text-gray-800 mb-2">Results for: {selectedBacktest.name}</h4>
                  <p className="text-sm text-gray-600">Total data points: {backtestResults.data.results?.length || 0}</p>
                  <p className="text-xs text-gray-500 mt-1">💡 Download button exports all {backtestResults.data.results?.length || 0} results as Excel (DateTime + Net Premium only)</p>
                </div>
                
                {/* Leg Details Section */}
                {selectedBacktest.legs && selectedBacktest.legs.length > 0 && (
                  <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                    <h5 className="font-medium text-blue-800 mb-3 flex items-center">
                      <BarChart3 className="mr-2 h-4 w-4" />
                      Option Legs Used in This Backtest
                    </h5>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {selectedBacktest.legs.map((leg, index) => (
                        <div key={index} className="bg-white p-3 rounded border border-blue-200">
                          <div className="flex items-center justify-between mb-2">
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              leg.action === 'Buy' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                            }`}>
                              {leg.action}
                            </span>
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              leg.option_type === 'CE' ? 'bg-blue-100 text-blue-800' : 'bg-orange-100 text-orange-800'
                            }`}>
                              {leg.option_type}
                            </span>
                          </div>
                          <div className="space-y-1 text-sm">
                            <div className="flex justify-between">
                              <span className="text-gray-600">Index:</span>
                              <span className={`font-medium px-2 py-1 rounded text-xs ${
                                leg.index_name === 'NIFTY' ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'
                              }`}>
                                {leg.index_name}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600">Strike:</span>
                              <span className="font-medium">₹{leg.strike}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600">Expiry:</span>
                              <span className="font-medium">{new Date(leg.expiry).toLocaleDateString('en-IN')}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600">Lots:</span>
                              <span className="font-medium">{leg.lots}</span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {backtestResults.data.results && backtestResults.data.results.length > 0 ? (
                  <div className="overflow-x-auto">
                    <div className="mb-4 flex justify-between items-center">
                      <div className="text-sm text-gray-600">
                        {showAllResults 
                          ? `Showing all ${backtestResults.data.results.length} results`
                          : `Showing first 20 results of ${backtestResults.data.results.length} total`
                        }
                      </div>
                      {!showAllResults && backtestResults.data.results.length > 20 && (
                        <button
                          onClick={() => setShowAllResults(true)}
                          className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
                        >
                          View All Results
                        </button>
                      )}
                      {showAllResults && (
                        <button
                          onClick={() => setShowAllResults(false)}
                          className="px-3 py-1 bg-gray-600 text-white rounded text-sm hover:bg-gray-700"
                        >
                          Show First 20
                        </button>
                      )}
                    </div>
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Net Premium</th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Volume</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {(showAllResults ? backtestResults.data.results : backtestResults.data.results.slice(0, 20)).map((result, index) => (
                          <tr key={index} className="hover:bg-gray-50">
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {new Date(result.datetime).toLocaleString('en-IN')}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              ₹{result.net_premium?.toFixed(2) || 'N/A'}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {result.volume || 'N/A'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <AlertCircle className="mx-auto h-12 w-12 mb-4" />
                    <p>No results found for this backtest.</p>
                    <p className="text-sm">The backtest may not have completed successfully.</p>
                  </div>
                )}
              </div>
            )}
            
            {loadingSummary && showSummary && selectedBacktest && (
              <div className="mt-8 p-6 bg-white rounded-lg shadow-lg">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-xl font-bold text-gray-900">Backtest Summary</h3>
                  <button
                    onClick={() => {
                      setShowSummary(false);
                      setSelectedBacktest(null);
                    }}
                    className="text-gray-500 hover:text-gray-700"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
                <div className="mb-4">
                  <h4 className="font-semibold text-gray-800 mb-2">Summary for: {selectedBacktest.name}</h4>
                </div>
                
                {/* Leg Details Section in Summary */}
                {selectedBacktest.legs && selectedBacktest.legs.length > 0 && (
                  <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                    <h5 className="font-medium text-blue-800 mb-3 flex items-center">
                      <BarChart3 className="mr-2 h-4 w-4" />
                      Option Legs Used in This Backtest
                    </h5>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {selectedBacktest.legs.map((leg, index) => (
                        <div key={index} className="bg-white p-3 rounded border border-blue-200">
                          <div className="flex items-center justify-between mb-2">
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              leg.action === 'Buy' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                            }`}>
                              {leg.action}
                            </span>
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              leg.option_type === 'CE' ? 'bg-blue-100 text-blue-800' : 'bg-orange-100 text-orange-800'
                            }`}>
                              {leg.option_type}
                            </span>
                          </div>
                          <div className="space-y-1 text-sm">
                            <div className="flex justify-between">
                              <span className="text-gray-600">Index:</span>
                              <span className={`font-medium px-2 py-1 rounded text-xs ${
                                leg.index_name === 'NIFTY' ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'
                              }`}>
                                {leg.index_name}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600">Strike:</span>
                              <span className="font-medium">₹{leg.strike}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600">Expiry:</span>
                              <span className="font-medium">{new Date(leg.expiry).toLocaleDateString('en-IN')}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600">Lots:</span>
                              <span className="font-medium">{leg.lots}</span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <h5 className="font-medium text-gray-700 mb-2">Performance</h5>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Total P&L:</span>
                        <span className={`font-medium ${backtestSummary.data.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          ₹{backtestSummary.data.total_pnl?.toFixed(2) || 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Win Rate:</span>
                        <span className="font-medium text-gray-900">
                          {backtestSummary.data.win_rate?.toFixed(1) || 'N/A'}%
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Total Minutes:</span>
                        <span className="font-medium text-gray-900">
                          {backtestSummary.data.total_minutes || 'N/A'}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <h5 className="font-medium text-gray-700 mb-2">Net Premium</h5>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Start:</span>
                        <span className="font-medium text-gray-900">
                          ₹{backtestSummary.data.net_premium_start?.toFixed(2) || 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">End:</span>
                        <span className="font-medium text-gray-900">
                          ₹{backtestSummary.data.net_premium_end?.toFixed(2) || 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Range:</span>
                        <span className="font-medium text-gray-900">
                          ₹{backtestSummary.data.net_premium_range?.min?.toFixed(2) || 'N/A'} - ₹{backtestSummary.data.net_premium_range?.max?.toFixed(2) || 'N/A'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            {/* Error Display for Failed Backtests */}
            {selectedBacktest && selectedBacktest.status === 'failed' && !showResults && !showSummary && (
              <div className="mt-8 p-6 bg-white rounded-lg shadow-lg">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-xl font-bold text-red-900">Backtest Failed</h3>
                  <button
                    onClick={() => {
                      setSelectedBacktest(null);
                    }}
                    className="text-gray-500 hover:text-gray-700"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
                
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
                  <div className="flex items-start">
                    <XCircle className="h-5 w-5 text-red-600 mt-0.5 mr-3 flex-shrink-0" />
                    <div>
                      <h4 className="font-medium text-red-800 mb-2">Backtest: {selectedBacktest.name}</h4>
                      <p className="text-red-700 text-sm">
                        This backtest failed because no market data was available for the selected date ({formatDate(selectedBacktest.backtest_date)}).
                      </p>
                      <p className="text-red-600 text-xs mt-2">
                        <strong>Common reasons:</strong> Weekend, holiday, or data not collected for that date.
                      </p>
                    </div>
                  </div>
                </div>
                
                {/* Leg Details Section */}
                {selectedBacktest.legs && selectedBacktest.legs.length > 0 && (
                  <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                    <h5 className="font-medium text-blue-800 mb-3 flex items-center">
                      <BarChart3 className="mr-2 h-4 w-4" />
                      Option Legs That Were Attempted
                    </h5>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {selectedBacktest.legs.map((leg, index) => (
                        <div key={index} className="bg-white p-3 rounded border border-blue-200">
                          <div className="flex items-center justify-between mb-2">
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              leg.action === 'Buy' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                            }`}>
                              {leg.action}
                            </span>
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              leg.option_type === 'CE' ? 'bg-blue-100 text-blue-800' : 'bg-orange-100 text-orange-800'
                            }`}>
                              {leg.option_type}
                            </span>
                          </div>
                          <div className="space-y-1 text-sm">
                            <div className="flex justify-between">
                              <span className="text-gray-600">Index:</span>
                              <span className={`font-medium px-2 py-1 rounded text-xs ${
                                leg.index_name === 'NIFTY' ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'
                              }`}>
                                {leg.index_name}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600">Strike:</span>
                              <span className="font-medium">₹{leg.strike}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600">Expiry:</span>
                              <span className="font-medium">{new Date(leg.expiry).toLocaleDateString('en-IN')}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600">Lots:</span>
                              <span className="font-medium">{leg.lots}</span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                <div className="text-center">
                  <p className="text-sm text-gray-600 mb-4">
                    Try selecting a different date that has market data available.
                  </p>
                  <button
                    onClick={() => setSelectedBacktest(null)}
                    className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500"
                  >
                    Close
                  </button>
                </div>
              </div>
            )}
          </>
        ) : (
          /* Show placeholder when not connected */
          <div className="text-center py-12 text-gray-500">
            <BarChart3 className="mx-auto h-16 w-16 text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Historical Backtesting</h3>
            <p className="text-sm">
              {connectionStatus === 'checking' 
                ? 'Checking connection to historical data service...' 
                : 'Unable to connect to historical data service. Please check your backend configuration.'
              }
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default HistoricalBacktest;