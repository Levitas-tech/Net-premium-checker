import React from 'react';
import { TrendingUp, TrendingDown, AlertCircle, Edit, Trash2 } from 'lucide-react';
import { format } from 'date-fns';

const OptionLegCard = ({ leg, isTracking, onEdit, onDelete }) => {
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

  const getSymbol = () => {
    return `${leg.index_name} ${formatNumber(leg.strike)} ${leg.option_type}`;
  };

  const getExpiryText = () => {
    if (!leg.expiry) return 'N/A';
    return format(new Date(leg.expiry), 'dd MMM yyyy');
  };

  return (
    <div className="card hover:shadow-md transition-shadow duration-200">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <div className={`px-2 py-1 rounded-full text-xs font-medium ${getActionBgColor(leg.action)} ${getActionColor(leg.action)}`}>
            {leg.action}
          </div>
          <div className="text-sm text-gray-500">
            {leg.lots} {leg.lots === 1 ? 'Lot' : 'Lots'}
          </div>
        </div>
        <div className="flex items-center space-x-2">
          {isTracking && (
            <div className="flex items-center space-x-1">
              <div className="w-2 h-2 bg-success-500 rounded-full animate-pulse"></div>
              <span className="text-xs text-gray-500">Live</span>
            </div>
          )}
          {onEdit && (
            <button
              onClick={() => onEdit(leg)}
              className="p-1 text-blue-600 hover:text-blue-800 transition-colors"
              title="Edit Leg"
            >
              <Edit className="h-4 w-4" />
            </button>
          )}
          {onDelete && (
            <button
              onClick={() => onDelete(leg.id)}
              className="p-1 text-red-600 hover:text-red-800 transition-colors"
              title="Delete Leg"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Symbol and Details */}
      <div className="space-y-3">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            {getSymbol()}
          </h3>
          <p className="text-sm text-gray-500">
            Expiry: {getExpiryText()}
          </p>
        </div>

        {/* Price Information */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              Current Price
            </label>
            <div className="text-lg font-semibold text-gray-900">
              {leg.current_price ? (
                formatCurrency(leg.current_price)
              ) : (
                <div className="flex items-center space-x-1">
                  <AlertCircle className="h-4 w-4 text-gray-400" />
                  <span className="text-gray-400">No Data</span>
                </div>
              )}
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              Current Value
            </label>
            <div className="text-lg font-semibold text-gray-900">
              {leg.current_value !== null && leg.current_value !== undefined ? (
                formatCurrency(leg.current_value)
              ) : (
                <span className="text-gray-400">--</span>
              )}
            </div>
          </div>
        </div>

        {/* Additional Details */}
        <div className="pt-3 border-t border-gray-200">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Strike:</span>
              <span className="ml-1 font-medium">{formatNumber(leg.strike)}</span>
            </div>
            <div>
              <span className="text-gray-500">Type:</span>
              <span className="ml-1 font-medium">{leg.option_type}</span>
            </div>
          </div>
        </div>

        {/* Premium Calculation: Buy => negative (debit), Sell => positive (credit) */}
        {leg.current_price && (
          <div className="pt-3 border-t border-gray-200">
            <div className="text-sm">
              <span className="text-gray-500">Premium:</span>
              <span className="ml-1 font-medium">
                {(() => {
                  const lotSize = leg.index_name === 'NIFTY' ? 75 : 20;
                  const raw = leg.current_price * leg.lots * lotSize;
                  const signed = leg.action === 'Buy' ? -raw : raw;
                  return formatCurrency(signed);
                })()}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default OptionLegCard; 