import React, { useState, useEffect } from 'react';
import { useQuery } from 'react-query';
import axios from 'axios';
import { X, Plus, Trash2 } from 'lucide-react';
import { format } from 'date-fns';
import CustomDropdown from '../ui/CustomDropdown';

const OptionLegForm = ({ onSave, onCancel, existingLegs = [] }) => {
  const [legs, setLegs] = useState([
    {
      index_name: 'NIFTY',
      strike: '',  // Start with empty value
      option_type: 'CE',
      expiry: '',
      action: 'Buy',
      lots: 1,
      price: null,
    }
  ]);

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

  const updateLeg = async (index, field, value) => {
    const updatedLegs = [...legs];
    updatedLegs[index] = { ...updatedLegs[index], [field]: value };
    setLegs(updatedLegs);

    // Fetch price when relevant fields change
    const leg = updatedLegs[index];
    if (field === 'index_name' || field === 'strike' || field === 'option_type' || field === 'expiry') {
      if (leg.index_name && leg.strike && leg.option_type && leg.expiry) {
        const price = await fetchOptionPrice(leg.index_name, leg.strike, leg.option_type, leg.expiry);
        updatedLegs[index] = { ...updatedLegs[index], price: price || null };
        setLegs([...updatedLegs]);
      }
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Validate form
    const isValid = legs.every(leg => 
      leg.index_name && leg.strike && leg.option_type && leg.expiry && leg.action && leg.lots
    );

    if (!isValid) {
      alert('Please fill in all fields');
      return;
    }

    // Save only the first leg (since we're now adding one leg at a time)
    const legData = {
      ...legs[0],
      expiry: new Date(legs[0].expiry),
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
          <h3 className="text-lg font-medium text-gray-900">Add Option Leg</h3>
          <button
            onClick={onCancel}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {legs.map((leg, index) => (
            <div key={index} className="card border-2 border-gray-200">
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-md font-medium text-gray-900">
                  Option Leg
                </h4>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {/* Index */}
                <div className="form-group">
                  <label className="form-label">Index</label>
                  <select
                    className="select"
                    value={leg.index_name}
                    onChange={(e) => updateLeg(index, 'index_name', e.target.value)}
                  >
                    <option value="NIFTY">NIFTY</option>
                    <option value="SENSEX">SENSEX</option>
                  </select>
                </div>

                {/* Strike */}
                <div className="form-group">
                  <label className="form-label">Strike Price</label>
                  <CustomDropdown
                    value={leg.strike || ''}
                    onChange={(value) => updateLeg(index, 'strike', value ? parseFloat(value) : '')}
                    options={getStrikesForIndex(leg.index_name)?.map(strike => ({
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
                    value={leg.option_type}
                    onChange={(e) => updateLeg(index, 'option_type', e.target.value)}
                  >
                    <option value="CE">Call (CE)</option>
                    <option value="PE">Put (PE)</option>
                  </select>
                </div>

                {/* Expiry */}
                <div className="form-group">
                  <label className="form-label">Expiry Date</label>
                  <CustomDropdown
                    value={leg.expiry}
                    onChange={(value) => updateLeg(index, 'expiry', value)}
                    options={getExpiriesForIndex(leg.index_name)?.map(expiry => ({
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
                    value={leg.action}
                    onChange={(e) => updateLeg(index, 'action', e.target.value)}
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
                    value={leg.lots || 1}
                    onChange={(e) => updateLeg(index, 'lots', parseInt(e.target.value) || 1)}
                  />
                </div>

                {/* Price */}
                <div className="form-group lg:col-span-3">
                  <label className="form-label">Current Price</label>
                  <div className="flex items-center space-x-2">
                    <input
                      type="text"
                      className="input bg-gray-50"
                      value={formatCurrency(leg.price)}
                      readOnly
                    />
                    {leg.price && leg.price > 0 && (
                      <span className="text-sm text-gray-500">
                        Total: {formatCurrency(leg.price * leg.lots * (leg.index_name === 'NIFTY' ? 75 : 20))}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}

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
              Save
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default OptionLegForm; 