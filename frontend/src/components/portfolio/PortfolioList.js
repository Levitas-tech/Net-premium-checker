import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import axios from 'axios';
import { Plus, Edit, Trash2, Eye } from 'lucide-react';

const PortfolioList = ({ onSelectPortfolio }) => {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newPortfolio, setNewPortfolio] = useState({ name: '', description: '' });
  
  const queryClient = useQueryClient();

  // Fetch portfolios
  const { data: portfolios, isLoading } = useQuery(
    'portfolios',
    async () => {
      const response = await axios.get('/portfolios');
      return response.data;
    }
  );

  // Create portfolio mutation
  const createPortfolioMutation = useMutation(
    async (portfolioData) => {
      const response = await axios.post('/portfolios', portfolioData);
      return response.data;
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries('portfolios');
        setShowCreateForm(false);
        setNewPortfolio({ name: '', description: '' });
      },
    }
  );

  // Delete portfolio mutation
  const deletePortfolioMutation = useMutation(
    async (portfolioId) => {
      await axios.delete(`/portfolios/${portfolioId}`);
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries('portfolios');
      },
    }
  );

  const handleCreatePortfolio = (e) => {
    e.preventDefault();
    if (newPortfolio.name.trim()) {
      createPortfolioMutation.mutate(newPortfolio);
    }
  };

  const handleDeletePortfolio = (portfolioId) => {
    if (window.confirm('Are you sure you want to delete this portfolio?')) {
      deletePortfolioMutation.mutate(portfolioId);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">Portfolios</h2>
        <button
          onClick={() => setShowCreateForm(true)}
          className="btn-primary flex items-center space-x-2"
        >
          <Plus className="h-4 w-4" />
          <span>New Portfolio</span>
        </button>
      </div>

      {/* Create Portfolio Form */}
      {showCreateForm && (
        <div className="bg-white rounded-lg shadow p-4 border">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Create New Portfolio</h3>
          <form onSubmit={handleCreatePortfolio} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Portfolio Name
              </label>
              <input
                type="text"
                value={newPortfolio.name}
                onChange={(e) => setNewPortfolio({ ...newPortfolio, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="Enter portfolio name"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description (Optional)
              </label>
              <textarea
                value={newPortfolio.description}
                onChange={(e) => setNewPortfolio({ ...newPortfolio, description: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="Enter description"
                rows="3"
              />
            </div>
            <div className="flex space-x-3">
              <button
                type="submit"
                disabled={createPortfolioMutation.isLoading}
                className="btn-primary"
              >
                {createPortfolioMutation.isLoading ? 'Creating...' : 'Create Portfolio'}
              </button>
              <button
                type="button"
                onClick={() => setShowCreateForm(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Portfolio List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {portfolios?.map((portfolio) => (
          <div key={portfolio.id} className="bg-white rounded-lg shadow p-4 border">
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1">
                <h3 className="text-lg font-medium text-gray-900">{portfolio.name}</h3>
                {portfolio.description && (
                  <p className="text-sm text-gray-600 mt-1">{portfolio.description}</p>
                )}
              </div>
              <div className="flex space-x-2">
                <button
                  onClick={() => onSelectPortfolio(portfolio)}
                  className="p-1 text-blue-600 hover:text-blue-800"
                  title="View Portfolio"
                >
                  <Eye className="h-4 w-4" />
                </button>
                <button
                  onClick={() => handleDeletePortfolio(portfolio.id)}
                  disabled={deletePortfolioMutation.isLoading}
                  className="p-1 text-red-600 hover:text-red-800"
                  title="Delete Portfolio"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
            <div className="text-xs text-gray-500">
              Created: {new Date(portfolio.created_at).toLocaleDateString()}
            </div>
            <div className="text-xs text-gray-500">
              Legs: {portfolio.option_legs_count || 0}
            </div>
          </div>
        ))}
      </div>

      {/* Empty State */}
      {portfolios?.length === 0 && (
        <div className="text-center py-8">
          <div className="mx-auto h-12 w-12 text-gray-400 mb-4">
            <Plus className="h-12 w-12" />
          </div>
          <h3 className="text-sm font-medium text-gray-900 mb-2">No portfolios yet</h3>
          <p className="text-sm text-gray-500 mb-4">
            Create your first portfolio to start managing option legs.
          </p>
          <button
            onClick={() => setShowCreateForm(true)}
            className="btn-primary inline-flex items-center space-x-2"
          >
            <Plus className="h-4 w-4" />
            <span>Create Portfolio</span>
          </button>
        </div>
      )}
    </div>
  );
};

export default PortfolioList; 