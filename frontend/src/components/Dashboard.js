import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import axios from 'axios';

import { 
  Plus, 
  Save, 
  Play,
  Pause, 
  TrendingUp, 
  TrendingDown,
  RefreshCw,
  AlertCircle,
  Activity
} from 'lucide-react';
import PortfolioList from './portfolio/PortfolioList';
import PortfolioView from './portfolio/PortfolioView';

const Dashboard = () => {
  const [selectedPortfolio, setSelectedPortfolio] = useState(null);
  const [websocketStatus, setWebsocketStatus] = useState(null);
  const [isWebsocketRunning, setIsWebsocketRunning] = useState(false);
  
  const queryClient = useQueryClient();

  // WebSocket status query
  const { data: wsStatus, refetch: refetchWsStatus, error: wsError } = useQuery(
    'websocketStatus',
    async () => {
      const response = await axios.get('/websocket/status/public');
      return response.data;
    },
    {
      refetchInterval: 5000, // Poll every 5 seconds
      enabled: true,
    }
  );

  // Update WebSocket status when data changes
  useEffect(() => {
    if (wsStatus) {
      setIsWebsocketRunning(wsStatus.is_running || false);
      setWebsocketStatus(wsStatus);
    }
  }, [wsStatus]);

  // Handle WebSocket errors
  useEffect(() => {
    if (wsError) {
      console.error('WebSocket status error:', wsError);
      setIsWebsocketRunning(false);
    }
  }, [wsError]);

  const handleSelectPortfolio = (portfolio) => {
    setSelectedPortfolio(portfolio);
  };

  const handleBackToPortfolios = () => {
    setSelectedPortfolio(null);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Options Trading Dashboard</h1>
          <p className="text-gray-600">Manage your portfolios and track live prices</p>
        </div>
        <div className="flex items-center space-x-3">
          {/* WebSocket Control */}
          <div className="flex items-center space-x-2 bg-gray-100 rounded-lg p-2">
            <Activity className={`h-4 w-4 ${isWebsocketRunning ? 'text-green-600' : 'text-gray-400'}`} />
            <span className="text-sm font-medium">
              {isWebsocketRunning ? 'WebSocket Running' : 'WebSocket Stopped'}
            </span>
            {wsError && (
              <div className="flex items-center text-red-500 text-xs">
                <AlertCircle className="h-3 w-3 mr-1" />
                WebSocket Error: {wsError.message || 'Unknown error'}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* WebSocket Status */}
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-3">WebSocket Status</h3>
        
        {/* Error Display */}
        {wsError && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center space-x-2">
              <AlertCircle className="h-5 w-5 text-red-500" />
              <span className="text-sm font-medium text-red-800">WebSocket Error</span>
            </div>
            <p className="text-sm text-red-700 mt-1">
              {wsError.message || 'Unable to connect to WebSocket service'}
            </p>
          </div>
        )}
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex items-center space-x-2">
            <div className={`w-3 h-3 rounded-full ${isWebsocketRunning ? 'bg-green-500' : 'bg-red-400'}`}></div>
            <span className="text-sm font-medium">
              Status: {isWebsocketRunning ? 'Running' : 'Stopped'}
            </span>
          </div>
          <div className="text-sm">
            <span className="font-medium">Queue Size:</span> {websocketStatus?.queue_size || 0}
          </div>
          <div className="text-sm">
            <span className="font-medium">Zerodha:</span> {websocketStatus?.zerodha_connected ? 'Connected' : 'Disconnected'}
          </div>
        </div>
        
        {websocketStatus?.worker_stats && Object.keys(websocketStatus.worker_stats).length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Worker Statistics</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              {Object.entries(websocketStatus.worker_stats).map(([workerId, stats]) => (
                <div key={workerId} className="bg-gray-50 p-2 rounded">
                  <div className="font-medium">Worker {workerId}</div>
                  <div>Batches: {stats.batches_processed || 0}</div>
                  <div>Ticks: {stats.total_ticks || 0}</div>
                  <div>Errors: {stats.errors || 0}</div>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Auto-start message */}
        {!isWebsocketRunning && !wsError && (
          <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-center space-x-2">
              <Activity className="h-4 w-4 text-blue-500" />
              <span className="text-sm font-medium text-blue-800">Auto-start</span>
            </div>
            <p className="text-sm text-blue-700 mt-1">
              WebSocket will start automatically during market hours (9:15 AM - 3:31 PM IST)
            </p>
          </div>
        )}
      </div>

      {/* Portfolio Management */}
      {selectedPortfolio ? (
        <PortfolioView 
          portfolio={selectedPortfolio} 
          onBack={handleBackToPortfolios}
        />
      ) : (
        <PortfolioList onSelectPortfolio={handleSelectPortfolio} />
      )}
    </div>
  );
};

export default Dashboard; 