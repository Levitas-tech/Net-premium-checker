import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import axios from 'axios';
import { ArrowLeft, Plus, RefreshCw } from 'lucide-react';
import OptionLegForm from '../trading/OptionLegForm';
import OptionLegEditForm from '../trading/OptionLegEditForm';
import OptionLegCard from '../trading/OptionLegCard';
import PnLSummary from '../trading/PnLSummary';

const PortfolioView = ({ portfolio, onBack }) => {
  const [showLegForm, setShowLegForm] = useState(false);
  const [showEditForm, setShowEditForm] = useState(false);
  const [editingLeg, setEditingLeg] = useState(null);
  const [isTracking, setIsTracking] = useState(false);
  const [legs, setLegs] = useState([]);
  const [netPremium, setNetPremium] = useState(0);
  const [totalPnl, setTotalPnl] = useState(0);
  const [lastUpdated, setLastUpdated] = useState(null);
  
  const queryClient = useQueryClient();

  // Fetch portfolio legs with live prices - OPTIMIZED
  const { data: portfolioData, isLoading: dataLoading } = useQuery(
    ['portfolioData', portfolio.id],
    async () => {
      // Just fetch prices endpoint which already includes legs with prices
      const response = await axios.get(`/portfolios/${portfolio.id}/prices`);
      return response.data;
    },
    {
      refetchInterval: isTracking ? 5000 : false, // 5-second polling
      staleTime: 2000, // Consider data stale after 2 seconds
      cacheTime: 10000, // Keep cache for 10 seconds
      enabled: !!portfolio.id,
    }
  );

  // Create option leg mutation
  const createLegMutation = useMutation(
    async (legData) => {
      const response = await axios.post(`/portfolios/${portfolio.id}/option-legs`, {
        ...legData,
        portfolio_id: portfolio.id
      });
      return response.data;
    },
    {
      onSuccess: () => {
        // Immediately refresh the prices/legs panel
        queryClient.invalidateQueries(['portfolioData', portfolio.id]);
        setShowLegForm(false);
      },
    }
  );

  // Update option leg mutation
  const updateLegMutation = useMutation(
    async ({ legId, legData }) => {
      const response = await axios.put(`/portfolios/${portfolio.id}/option-legs/${legId}`, legData);
      return response.data;
    },
    {
      onSuccess: () => {
        // Refresh portfolio data so UI updates without manual reload
        queryClient.invalidateQueries(['portfolioData', portfolio.id]);
        setShowEditForm(false);
        setEditingLeg(null);
      },
    }
  );

  // Delete option leg mutation
  const deleteLegMutation = useMutation(
    async (legId) => {
      await axios.delete(`/portfolios/${portfolio.id}/option-legs/${legId}`);
    },
    {
      onSuccess: () => {
        // Refresh after delete
        queryClient.invalidateQueries(['portfolioData', portfolio.id]);
      },
    }
  );

  // Update local state when data changes
  useEffect(() => {
    if (portfolioData) {
      // The prices endpoint already returns legs with current_price and current_value
      setLegs(portfolioData.legs || []);
      setNetPremium(portfolioData.net_premium || 0);
      setTotalPnl(portfolioData.total_pnl || 0);
      setLastUpdated(new Date(portfolioData.last_updated));
    }
  }, [portfolioData]);

  const handleCreateLeg = (legData) => {
    createLegMutation.mutate(legData);
  };

  const handleEditLeg = (leg) => {
    setEditingLeg(leg);
    setShowEditForm(true);
  };

  const handleUpdateLeg = (legData) => {
    updateLegMutation.mutate({
      legId: editingLeg.id,
      legData: legData
    });
  };

  const handleDeleteLeg = (legId) => {
    if (window.confirm('Are you sure you want to delete this option leg?')) {
      deleteLegMutation.mutate(legId);
    }
  };

  const handleStartTracking = () => {
    setIsTracking(true);
  };

  const handleStopTracking = () => {
    setIsTracking(false);
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2,
    }).format(amount);
  };

  if (dataLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button
            onClick={onBack}
            className="p-2 text-gray-600 hover:text-gray-800"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{portfolio.name}</h1>
            {portfolio.description && (
              <p className="text-gray-600">{portfolio.description}</p>
            )}
          </div>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setShowLegForm(true)}
            className="btn-primary flex items-center space-x-2"
          >
            <Plus className="h-4 w-4" />
            <span>Add Option Leg</span>
          </button>
          {legs.length > 0 && (
            <button
              onClick={isTracking ? handleStopTracking : handleStartTracking}
              className={`btn flex items-center space-x-2 ${
                isTracking ? 'btn-danger' : 'btn-success'
              }`}
            >
              <RefreshCw className={`h-4 w-4 ${isTracking ? 'animate-spin' : ''}`} />
              <span>{isTracking ? 'Stop Tracking' : 'Start Tracking'}</span>
            </button>
          )}
        </div>
      </div>

      {/* P&L Summary */}
      {legs.length > 0 && (
        <PnLSummary
          netPremium={netPremium}
          totalPnl={totalPnl}
          lastUpdated={lastUpdated}
          isTracking={isTracking}
        />
      )}

      {/* Option Legs Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        {legs.map((leg) => (
          <OptionLegCard
            key={leg.id}
            leg={leg}
            isTracking={isTracking}
            onEdit={handleEditLeg}
            onDelete={handleDeleteLeg}
          />
        ))}
      </div>

      {/* Empty State */}
      {legs.length === 0 && (
        <div className="text-center py-12">
          <div className="mx-auto h-12 w-12 text-gray-400">
            <Plus className="h-12 w-12" />
          </div>
          <h3 className="mt-2 text-sm font-medium text-gray-900">No option legs</h3>
          <p className="mt-1 text-sm text-gray-500">
            Get started by adding your first option leg to this portfolio.
          </p>
          <div className="mt-6">
            <button
              onClick={() => setShowLegForm(true)}
              className="btn-primary inline-flex items-center space-x-2"
            >
              <Plus className="h-4 w-4" />
              <span>Add Option Leg</span>
            </button>
          </div>
        </div>
      )}

      {/* Option Leg Form Modal */}
      {showLegForm && (
        <OptionLegForm
          onSave={handleCreateLeg}
          onCancel={() => setShowLegForm(false)}
          existingLegs={legs}
        />
      )}

      {/* Option Leg Edit Form Modal */}
      {showEditForm && editingLeg && (
        <OptionLegEditForm
          leg={editingLeg}
          onSave={handleUpdateLeg}
          onCancel={() => {
            setShowEditForm(false);
            setEditingLeg(null);
          }}
        />
      )}
    </div>
  );
};

export default PortfolioView; 