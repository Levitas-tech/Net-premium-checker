import React from 'react';
import { RefreshCw, TrendingUp, TrendingDown } from 'lucide-react';

const LivePricesPanel = ({ legs }) => {
  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2,
    }).format(amount);
  };

  const formatNumber = (number) => {
    return new Intl.NumberFormat('en-IN').format(number);
  };

  const getActionColor = (action) => {
    return action === 'Buy' ? 'text-success-600' : 'text-danger-600';
  };

  const getActionBgColor = (action) => {
    return action === 'Buy' ? 'bg-success-100' : 'bg-danger-100';
  };

  const getPnlColor = (pnl) => {
    if (!pnl) return 'text-gray-500';
    return pnl > 0 ? 'text-success-600' : pnl < 0 ? 'text-danger-600' : 'text-gray-500';
  };

  const getPnlIcon = (pnl) => {
    if (!pnl) return null;
    return pnl > 0 ? (
      <TrendingUp className="h-4 w-4 text-success-600" />
    ) : pnl < 0 ? (
      <TrendingDown className="h-4 w-4 text-danger-600" />
    ) : null;
  };

  const getSymbol = (leg) => {
    return `${leg.index_name} ${formatNumber(leg.strike)} ${leg.option_type}`;
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-2">
          <RefreshCw className="h-5 w-5 text-success-500 animate-spin" />
          <h3 className="text-lg font-semibold text-gray-900">Live Prices</h3>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 bg-success-500 rounded-full animate-pulse"></div>
          <span className="text-sm text-success-600 font-medium">Live Updates</span>
        </div>
      </div>

      <div className="space-y-4">
        {legs.map((leg) => (
          <div
            key={leg.id}
            className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-200"
          >
            {/* Symbol and Action */}
            <div className="flex items-center space-x-4">
              <div>
                <h4 className="font-medium text-gray-900">
                  {getSymbol(leg)}
                </h4>
                <p className="text-sm text-gray-500">
                  {leg.lots} {leg.lots === 1 ? 'Lot' : 'Lots'}
                </p>
              </div>
              <div className={`px-3 py-1 rounded-full text-xs font-medium ${getActionBgColor(leg.action)} ${getActionColor(leg.action)}`}>
                {leg.action}
              </div>
            </div>

            {/* Price and P&L */}
            <div className="flex items-center space-x-6">
              {/* Current Price */}
              <div className="text-right">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Current Price
                </p>
                <p className="text-lg font-semibold text-gray-900">
                  {leg.current_price ? (
                    formatCurrency(leg.current_price)
                  ) : (
                    <span className="text-gray-400">--</span>
                  )}
                </p>
              </div>

              {/* P&L */}
              <div className="text-right">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                  P&L
                </p>
                <div className={`text-lg font-semibold flex items-center justify-end space-x-1 ${getPnlColor(leg.pnl)}`}>
                  {getPnlIcon(leg.pnl)}
                  <span>
                    {leg.pnl !== null && leg.pnl !== undefined ? (
                      formatCurrency(leg.pnl)
                    ) : (
                      <span className="text-gray-400">--</span>
                    )}
                  </span>
                </div>
              </div>

              {/* Premium */}
              <div className="text-right">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Premium
                </p>
                <p className="text-lg font-semibold text-gray-900">
                  {leg.current_price ? (
                    formatCurrency(leg.current_price * leg.lots * 100)
                  ) : (
                    <span className="text-gray-400">--</span>
                  )}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Summary */}
      <div className="mt-6 pt-6 border-t border-gray-200">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              Total Legs
            </p>
            <p className="text-2xl font-bold text-gray-900">
              {legs.length}
            </p>
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              Active Prices
            </p>
            <p className="text-2xl font-bold text-gray-900">
              {legs.filter(leg => leg.current_price).length}
            </p>
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              Update Frequency
            </p>
            <p className="text-2xl font-bold text-gray-900">
              2s
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LivePricesPanel; 