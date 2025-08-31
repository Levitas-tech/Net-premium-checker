import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import axios from 'axios';
import { 
  Users, 
  UserPlus, 
  Edit, 
  Trash2, 
  Shield, 
  User, 
  X, 
  Check, 
  AlertCircle,
  Eye,
  EyeOff,
  BarChart3
} from 'lucide-react';

const AdminPanel = () => {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [showPassword, setShowPassword] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  
  const queryClient = useQueryClient();

  // Form state
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    is_admin: false
  });

  // Check if current user is admin
  const { data: adminStatus, isLoading: loadingAdminStatus } = useQuery(
    'admin-status',
    () => axios.get('/admin/check'),
    {
      onError: () => {
        // If this fails, user is not admin
      }
    }
  );

  // Get all users
  const { data: users, isLoading: loadingUsers, error: usersError } = useQuery(
    'admin-users',
    () => axios.get('/admin/users'),
    {
      enabled: adminStatus?.data?.is_admin === true,
      onError: (error) => {
        if (error.response?.status === 403) {
          setErrorMessage('Access denied. Admin privileges required.');
        }
      }
    }
  );

  // Get all backtests
  const { data: backtests, isLoading: loadingBacktests, error: backtestsError } = useQuery(
    'admin-backtests',
    () => axios.get('/admin/backtests'),
    {
      enabled: adminStatus?.data?.is_admin === true,
      onError: (error) => {
        if (error.response?.status === 403) {
          setErrorMessage('Access denied. Admin privileges required to view backtests.');
        }
      }
    }
  );

  // Create user mutation
  const createUserMutation = useMutation(
    (userData) => axios.post('/admin/users', userData),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('admin-users');
        setSuccessMessage('User created successfully!');
        setShowCreateForm(false);
        resetForm();
        setTimeout(() => setSuccessMessage(''), 5000);
      },
      onError: (error) => {
        const message = error.response?.data?.detail || 'Failed to create user';
        setErrorMessage(message);
        setTimeout(() => setErrorMessage(''), 5000);
      }
    }
  );

  // Update user mutation
  const updateUserMutation = useMutation(
    ({ userId, userData }) => axios.put(`/admin/users/${userId}`, userData),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('admin-users');
        setSuccessMessage('User updated successfully!');
        setEditingUser(null);
        resetForm();
        setTimeout(() => setSuccessMessage(''), 5000);
      },
      onError: (error) => {
        const message = error.response?.data?.detail || 'Failed to update user';
        setErrorMessage(message);
        setTimeout(() => setErrorMessage(''), 5000);
      }
    }
  );

  // Delete user mutation
  const deleteUserMutation = useMutation(
    (userId) => axios.delete(`/admin/users/${userId}`),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('admin-users');
        setSuccessMessage('User deleted successfully!');
        setTimeout(() => setSuccessMessage(''), 5000);
      },
      onError: (error) => {
        const message = error.response?.data?.detail || 'Failed to delete user';
        setErrorMessage(message);
        setTimeout(() => setErrorMessage(''), 5000);
      }
    }
  );

  const [selectedUserId, setSelectedUserId] = useState('all');

  const handleDelete = (userId, username) => {
    if (window.confirm(`Are you sure you want to delete user "${username}"? This action cannot be undone.`)) {
      deleteUserMutation.mutate(userId);
    }
  };

  // Filter backtests by selected user
  const filteredBacktests = React.useMemo(() => {
    if (!backtests?.data || selectedUserId === 'all') {
      return backtests?.data || [];
    }
    return backtests.data.filter(backtest => backtest.user_id === parseInt(selectedUserId));
  }, [backtests?.data, selectedUserId]);

  const cancelEdit = () => {
    setEditingUser(null);
    resetForm();
  };

  const resetForm = () => {
    setFormData({
      username: '',
      email: '',
      password: '',
      is_admin: false
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (editingUser) {
      updateUserMutation.mutate({ userId: editingUser.id, userData: formData });
    } else {
      createUserMutation.mutate(formData);
    }
  };

  const handleEdit = (user) => {
    setEditingUser(user);
    setFormData({
      username: user.username,
      email: user.email,
      password: '',
      is_admin: user.is_admin
    });
    setShowCreateForm(true);
  };

  if (loadingAdminStatus) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!adminStatus?.data?.is_admin) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Shield className="mx-auto h-12 w-12 text-red-500 mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Access Denied</h2>
          <p className="text-gray-600">You need admin privileges to access this page.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Admin Panel</h1>
        <p className="text-gray-600 mt-2">Manage users and monitor system activity</p>
      </div>

      {/* Success/Error Messages */}
      {successMessage && (
        <div className="mb-6 bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-md flex items-center">
          <Check className="h-5 w-5 mr-2" />
          {successMessage}
        </div>
      )}

      {errorMessage && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md flex items-center">
          <AlertCircle className="h-5 w-5 mr-2" />
          {errorMessage}
        </div>
      )}

      {/* User Management Section */}
      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center">
            <Users className="h-6 w-6 text-blue-600 mr-3" />
            <h2 className="text-xl font-semibold text-gray-900">User Management</h2>
          </div>
          <button
            onClick={() => setShowCreateForm(true)}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <UserPlus className="h-4 w-4 mr-2" />
            Add User
          </button>
        </div>

        {/* Create/Edit User Form */}
        {showCreateForm && (
          <div className="mb-6 p-4 border border-gray-200 rounded-lg bg-gray-50">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              {editingUser ? 'Edit User' : 'Create New User'}
            </h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="username" className="block text-sm font-medium text-gray-700">
                    Username
                  </label>
                  <input
                    type="text"
                    id="username"
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    required
                  />
                </div>
                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                    Email
                  </label>
                  <input
                    type="email"
                    id="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    required
                  />
                </div>
              </div>
              
              <div className="relative">
                <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                  Password {editingUser && <span className="text-gray-500">(leave blank to keep current)</span>}
                </label>
                <div className="mt-1 relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    id="password"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    className="block w-full px-3 py-2 pr-10 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    required={!editingUser}
                  />
                  <button
                    type="button"
                    className="absolute inset-y-0 right-0 pr-3 flex items-center"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4 text-gray-400" />
                    ) : (
                      <Eye className="h-4 w-4 text-gray-400" />
                    )}
                  </button>
                </div>
              </div>

              <div className="flex items-center">
                <input
                  id="is_admin"
                  type="checkbox"
                  checked={formData.is_admin}
                  onChange={(e) => setFormData({ ...formData, is_admin: e.target.checked })}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="is_admin" className="ml-2 block text-sm text-gray-900">
                  Admin privileges
                </label>
              </div>

              <div className="flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateForm(false);
                    cancelEdit();
                  }}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  <X className="h-4 w-4 mr-2 inline" />
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createUserMutation.isLoading || updateUserMutation.isLoading}
                  className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                >
                  {createUserMutation.isLoading || updateUserMutation.isLoading ? (
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2 inline-block"></div>
                  ) : (
                    <Check className="h-4 w-4 mr-2 inline" />
                  )}
                  {editingUser ? 'Update User' : 'Create User'}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Users List */}
        <div>
          {loadingUsers ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Loading users...</p>
            </div>
          ) : usersError ? (
            <div className="text-center py-8 text-red-600">
              <AlertCircle className="mx-auto h-12 w-8 mb-4" />
              <p>Error loading users. Please try again.</p>
            </div>
          ) : users?.data && users.data.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      User
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Role
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Created
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {users.data.map((user) => (
                    <tr key={user.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {user.username}
                          </div>
                          <div className="text-sm text-gray-500">
                            {user.email}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          user.is_admin 
                            ? 'bg-purple-100 text-purple-800' 
                            : 'bg-gray-100 text-gray-800'
                        }`}>
                          {user.is_admin ? (
                            <>
                              <Shield className="mr-1 h-3 w-3" />
                              Admin
                            </>
                          ) : (
                            <>
                              <User className="mr-1 h-3 w-3" />
                              User
                            </>
                          )}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(user.created_at).toLocaleDateString('en-IN')}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <div className="flex space-x-2">
                          <button
                            onClick={() => handleEdit(user)}
                            className="text-indigo-600 hover:text-indigo-900"
                            title="Edit user"
                          >
                            <Edit className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleDelete(user.id, user.username)}
                            className="text-red-600 hover:text-red-900"
                            title="Delete user"
                            disabled={deleteUserMutation.isLoading}
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <Users className="mx-auto h-12 w-12 text-gray-400 mb-4" />
              <p>No users found.</p>
            </div>
          )}
        </div>
      </div>

      {/* All Backtests Section */}
      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center">
            <BarChart3 className="h-6 w-6 text-blue-600 mr-3" />
            <h2 className="text-xl font-semibold text-gray-900">All Backtests</h2>
          </div>
          <div className="text-sm text-gray-500">
            {filteredBacktests ? `${filteredBacktests.length} backtests` : 'Loading...'}
          </div>
        </div>

        {/* User Filter Dropdown */}
        <div className="mb-6">
          <label htmlFor="user-filter" className="block text-sm font-medium text-gray-700 mb-2">
            Filter by User
          </label>
          <select
            id="user-filter"
            value={selectedUserId}
            onChange={(e) => setSelectedUserId(e.target.value)}
            className="block w-full max-w-xs px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
          >
            <option value="all">All Users ({backtests?.data?.length || 0} backtests)</option>
            {users?.data?.map((user) => (
              <option key={user.id} value={user.id}>
                {user.username} ({user.email}) - {backtests?.data?.filter(bt => bt.user_id === user.id).length || 0} backtests
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-4">
          {loadingBacktests ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Loading backtests...</p>
            </div>
          ) : backtestsError ? (
            <div className="text-center py-8 text-red-600">
              <AlertCircle className="mx-auto h-12 w-8 mb-4" />
              <p>Error loading backtests. Please try again.</p>
            </div>
          ) : filteredBacktests?.length > 0 ? (
            <div className="space-y-4">
              {filteredBacktests.map((backtest) => (
                <div key={backtest.id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-3 mb-2">
                        <h3 className="text-lg font-medium text-gray-900">{backtest.name}</h3>
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          backtest.status === 'completed' 
                            ? 'bg-green-100 text-green-800' 
                            : backtest.status === 'running'
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-red-100 text-red-800'
                        }`}>
                          {backtest.status}
                        </span>
                      </div>
                      
                      {backtest.description && (
                        <p className="text-gray-600 mb-3">{backtest.description}</p>
                      )}
                      
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <span className="text-gray-500">User:</span>
                          <div className="font-medium">{backtest.username}</div>
                          <div className="text-gray-500 text-xs">{backtest.email}</div>
                        </div>
                        <div>
                          <span className="text-gray-500">Date:</span>
                          <div className="font-medium">{new Date(backtest.backtest_date).toLocaleDateString('en-IN')}</div>
                        </div>
                        <div>
                          <span className="text-gray-500">Legs:</span>
                          <div className="font-medium">{backtest.total_legs}</div>
                        </div>
                        <div>
                          <span className="text-gray-500">Created:</span>
                          <div className="font-medium">{new Date(backtest.created_at).toLocaleDateString('en-IN')}</div>
                        </div>
                      </div>
                      
                      {backtest.net_premium_start !== null && backtest.net_premium_end !== null && (
                        <div className="mt-3 p-3 bg-gray-50 rounded-lg">
                          <div className="text-sm text-gray-600 mb-2">Net Premium Range:</div>
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <span className="text-gray-500 text-xs">Start:</span>
                              <div className="font-medium">₹{backtest.net_premium_start?.toFixed(2) || 'N/A'}</div>
                            </div>
                            <div>
                              <span className="text-gray-500 text-xs">End:</span>
                              <div className="font-medium">₹{backtest.net_premium_end?.toFixed(2) || 'N/A'}</div>
                            </div>
                          </div>
                        </div>
                      )}
                      
                      {backtest.legs && backtest.legs.length > 0 && (
                        <div className="mt-3">
                          <div className="text-sm text-gray-600 mb-2">Strategy Legs:</div>
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                            {backtest.legs.map((leg, index) => (
                              <div key={index} className="text-xs bg-blue-50 p-2 rounded border">
                                <div className="font-medium">{leg.index_name} {leg.strike} {leg.option_type}</div>
                                <div className="text-gray-600">{leg.action} {leg.lots} lots</div>
                                <div className="text-gray-500">Exp: {new Date(leg.expiry).toLocaleDateString('en-IN')}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <BarChart3 className="mx-auto h-12 w-12 text-gray-400 mb-4" />
              <p>No backtests found{selectedUserId !== 'all' ? ' for selected user' : ''}.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AdminPanel;
