import React, { useState, useEffect } from 'react';
import { useQuery } from 'react-query';
import axios from 'axios';
import { X } from 'lucide-react';
import { format } from 'date-fns';
import CustomDropdown from '../ui/CustomDropdown';

const OptionLegEditForm = ({ leg, onSave, onCancel }) => {
  const [formData, setFormData] = useState({
    index_name: leg.index_name || 'NIFTY',
    strike: leg.strike || 17000,
    option_type: leg.option_type || 'CE',
    expiry: leg.expiry ? format(new Date(leg.expiry), 'yyyy-MM-dd') : '',
    action: leg.action || 'Buy',
    lots: leg.lots || 1,
    price: leg.current_price || null,
  });

  // Fetch available strikes and expiries
  const { data: niftyStrikes } = useQuery(
    'niftyStrikes',
    () => axios.get('/available-strikes/NIFTY').then(res => res.data.strikes),
    { enabled: true }
  );

  const { data: sensexStrikes } = useQuery(
    'sensexStrikes',
    () => axios.get('/available-strikes/SENSEX').then(res => res.data.strikes),
    { enabled: true }
  );

  const { data: niftyExpiries } = useQuery(
    'niftyExpiries',
    () => axios.get('/available-expiries/NIFTY').then(res => res.data.expiries),
    { enabled: true }
  );

  const { data: sensexExpiries } = useQuery(
    'sensexExpiries',
    () => axios.get('/available-expiries/SENSEX').then(res => res.data.expiries),
    { enabled: true }
  );

  // Fetch option prices when leg details change
  const fetchOptionPrice = async (indexName, strike, optionType, expiry) => {
    if (!indexName || !strike || !optionType || !expiry) return null;
    
    try {
      const response = await axios.get(`/option-price/${indexName}`, {
        params: {
          strike: strike,
          option_type: optionType,
          expiry: expiry
        }
      });
      return response.data.price;
    } catch (error) {
      console.error('Error fetching option price:', error);
      return null;
    }
  };

  const updateField = async (field, value) => {
    const updatedData = { ...formData, [field]: value };
    setFormData(updatedData);

    // Fetch price when relevant fields change
    if (field === 'index_name' || field === 'strike' || field === 'option_type' || field === 'expiry') {
      if (updatedData.index_name && updatedData.strike && updatedData.option_type && updatedData.expiry) {
        const price = await fetchOptionPrice(updatedData.index_name, updatedData.strike, updatedData.option_type, updatedData.expiry);
        setFormData({ ...updatedData, price: price });
      }
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Validate form
    if (!formData.index_name || !formData.strike || !formData.option_type || !formData.expiry || !formData.action || !formData.lots) {
      alert('Please fill in all fields');
      return;
    }

    const legData = {
      ...formData,
      expiry: new Date(formData.expiry),
      entry_price: formData.price || 0,
    };
    
    onSave(legData);
  };

  const getStrikesForIndex = (indexName) => {
    return indexName === 'NIFTY' ? niftyStrikes : sensexStrikes;
  };

  const getExpiriesForIndex = (indexName) => {
    return indexName === 'NIFTY' ? niftyExpiries : sensexExpiries;
  };

  const formatCurrency = (amount) => {
    if (amount === null || amount === undefined) return '₹0.00';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(amount);
  };

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-20 mx-auto p-5 border w-11/12 md:w-3/4 lg:w-1/2 shadow-lg rounded-md bg-white">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-medium text-gray-900">Edit Option Leg</h3>
          <button
            onClick={onCancel}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="card border-2 border-gray-200 p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {/* Index */}
              <div className="form-group">
                <label className="form-label">Index</label>
                <select
                  className="select"
                  value={formData.index_name}
                  onChange={(e) => updateField('index_name', e.target.value)}
                >
                  <option value="NIFTY">NIFTY</option>
                  <option value="SENSEX">SENSEX</option>
                </select>
              </div>

              {/* Strike */}
              <div className="form-group">
                <label className="form-label">Strike Price</label>
                <CustomDropdown
                  value={formData.strike}
                  onChange={(value) => updateField('strike', parseFloat(value))}
                  options={getStrikesForIndex(formData.index_name)?.map(strike => ({
                    value: strike,
                    label: strike.toLocaleString('en-IN')
                  })) || []}
                  placeholder="Select Strike"
                />
              </div>

              {/* Option Type */}
              <div className="form-group">
                <label className="form-label">Option Type</label>
                <select
                  className="select"
                  value={formData.option_type}
                  onChange={(e) => updateField('option_type', e.target.value)}
                >
                  <option value="CE">Call (CE)</option>
                  <option value="PE">Put (PE)</option>
                </select>
              </div>

              {/* Expiry */}
              <div className="form-group">
                <label className="form-label">Expiry Date</label>
                <CustomDropdown
                  value={formData.expiry}
                  onChange={(value) => updateField('expiry', value)}
                  options={getExpiriesForIndex(formData.index_name)?.map(expiry => ({
                    value: expiry,
                    label: format(new Date(expiry), 'dd MMM yyyy')
                  })) || []}
                  placeholder="Select Expiry"
                />
              </div>

              {/* Action */}
              <div className="form-group">
                <label className="form-label">Action</label>
                <select
                  className="select"
                  value={formData.action}
                  onChange={(e) => updateField('action', e.target.value)}
                >
                  <option value="Buy">Buy</option>
                  <option value="Sell">Sell</option>
                </select>
              </div>

              {/* Lots */}
              <div className="form-group">
                <label className="form-label">Lots</label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  className="input"
                  value={formData.lots}
                  onChange={(e) => updateField('lots', parseInt(e.target.value))}
                />
              </div>

              {/* Price */}
              <div className="form-group lg:col-span-3">
                <label className="form-label">Current Price</label>
                <div className="flex items-center space-x-2">
                  <input
                    type="text"
                    className="input bg-gray-50"
                    value={formatCurrency(formData.price)}
                    readOnly
                  />
                  {formData.price && (
                    <span className="text-sm text-gray-500">
                      Total: {formatCurrency(formData.price * formData.lots * 50)}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="flex justify-end space-x-3 pt-6 border-t">
            <button
              type="button"
              onClick={onCancel}
              className="btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
            >
              Update
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default OptionLegEditForm; 