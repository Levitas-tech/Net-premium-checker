import React from 'react';
import { TrendingUp, TrendingDown, RefreshCw } from 'lucide-react';

const PnLSummary = ({ netPremium, totalPnl, lastUpdated, isTracking }) => {
  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2,
    }).format(amount);
  };

  const formatTime = (date) => {
    if (!date) return '';
    return new Intl.DateTimeFormat('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    }).format(new Date(date));
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Total Value */}
      <div className="card">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-500 uppercase tracking-wide">
              Total Value
            </p>
            <p className="text-2xl font-bold text-gray-900">
              {formatCurrency(totalPnl || netPremium)}
            </p>
          </div>
          {isTracking && (
            <div className="flex items-center space-x-1">
              <RefreshCw className="h-4 w-4 text-success-500 animate-spin" />
              <span className="text-xs text-success-600">Live</span>
            </div>
          )}
        </div>
        <div className="mt-2">
          <p className="text-xs text-gray-500">
            Current market value of all positions
          </p>
        </div>
      </div>

      {/* Last Updated */}
      <div className="card">
        <div>
          <p className="text-sm font-medium text-gray-500 uppercase tracking-wide">
            Last Updated
          </p>
          <p className="text-2xl font-bold text-gray-900">
            {lastUpdated ? formatTime(lastUpdated) : '--'}
          </p>
        </div>
        <div className="mt-2">
          <p className="text-xs text-gray-500">
            {isTracking ? 'Auto-refreshing every 5s' : 'Manual updates'}
          </p>
        </div>
      </div>
    </div>
  );
};

export default PnLSummary; 