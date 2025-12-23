import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Shield, Upload, FileText, Settings, LogOut, Sparkles, TrendingUp, AlertTriangle, CheckCircle } from 'lucide-react';
import api from '../utils/api';

const Dashboard = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [schemas, setSchemas] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSchemas();
  }, []);

  const fetchSchemas = async () => {
    try {
      const response = await api.get('/api/schemas/my-schemas');
      setSchemas(response.data);
    } catch (error) {
      console.error('Failed to fetch schemas:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Header */}
      <header className="glass border-b border-white/20 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl shadow-lg">
                <Shield className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold gradient-text">FlowGuard</h1>
                <p className="text-sm text-gray-600">API Testing & Stability Platform</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/settings')}
                className="p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all"
                title="Settings"
              >
                <Settings className="w-5 h-5" />
              </button>
              <button
                onClick={handleLogout}
                className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all"
                title="Logout"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Welcome Section */}
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-gray-800 mb-2">
            Welcome back, {user?.full_name?.split(' ')[0] || 'User'}! 👋
          </h2>
          <p className="text-gray-600">Manage your API schemas and test runs</p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="glass rounded-2xl p-6 backdrop-blur-xl border border-white/30">
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-blue-100 rounded-xl">
                <FileText className="w-6 h-6 text-blue-600" />
              </div>
              <TrendingUp className="w-5 h-5 text-green-500" />
            </div>
            <h3 className="text-2xl font-bold text-gray-800 mb-1">{schemas.length}</h3>
            <p className="text-sm text-gray-600">Total Schemas</p>
          </div>

          <div className="glass rounded-2xl p-6 backdrop-blur-xl border border-white/30">
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-green-100 rounded-xl">
                <CheckCircle className="w-6 h-6 text-green-600" />
              </div>
              <TrendingUp className="w-5 h-5 text-green-500" />
            </div>
            <h3 className="text-2xl font-bold text-gray-800 mb-1">
              {schemas.reduce((acc, s) => acc + (s.total_test_cases || 0), 0)}
            </h3>
            <p className="text-sm text-gray-600">Test Cases</p>
          </div>

          <div className="glass rounded-2xl p-6 backdrop-blur-xl border border-white/30">
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-purple-100 rounded-xl">
                <Sparkles className="w-6 h-6 text-purple-600" />
              </div>
              <TrendingUp className="w-5 h-5 text-green-500" />
            </div>
            <h3 className="text-2xl font-bold text-gray-800 mb-1">
              {schemas.reduce((acc, s) => acc + (s.total_endpoints || 0), 0)}
            </h3>
            <p className="text-sm text-gray-600">Endpoints</p>
          </div>
        </div>

        {/* Actions */}
        <div className="mb-8">
          <button
            onClick={() => navigate('/upload')}
            className="px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transform hover:scale-[1.02] transition-all duration-200 flex items-center gap-2"
          >
            <Upload className="w-5 h-5" />
            Upload New Schema
          </button>
        </div>

        {/* Schemas List */}
        <div className="glass rounded-2xl p-6 backdrop-blur-xl border border-white/30">
          <h3 className="text-xl font-semibold text-gray-800 mb-4">Your Schemas</h3>
          {loading ? (
            <div className="text-center py-12">
              <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
              <p className="text-gray-600">Loading schemas...</p>
            </div>
          ) : schemas.length === 0 ? (
            <div>
              <div className="text-center py-8">
                <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-600 mb-4">No schemas yet</p>
                <button
                  onClick={() => navigate('/upload')}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Upload Your First Schema
                </button>
              </div>

              {/* Example Schema Cards */}
              <div className="mt-8 border-t border-gray-200 pt-8">
                <h4 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-blue-600" />
                  Example: What You'll See After Upload
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Example Schema 1 */}
                  <div className="p-4 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl border border-blue-200">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <FileText className="w-5 h-5 text-blue-600" />
                        <h5 className="font-semibold text-gray-800">user-api.json</h5>
                      </div>
                      <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-lg font-medium">
                        Example
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mb-2">https://api.example.com</p>
                    <div className="flex items-center gap-3 text-xs text-gray-500">
                      <span>5 endpoints</span>
                      <span>•</span>
                      <span>12 test cases</span>
                    </div>
                  </div>

                  {/* Example Schema 2 */}
                  <div className="p-4 bg-gradient-to-br from-purple-50 to-pink-50 rounded-xl border border-purple-200">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <FileText className="w-5 h-5 text-purple-600" />
                        <h5 className="font-semibold text-gray-800">products-api.yaml</h5>
                      </div>
                      <span className="px-2 py-1 bg-purple-100 text-purple-700 text-xs rounded-lg font-medium">
                        Example
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mb-2">https://api.shop.com</p>
                    <div className="flex items-center gap-3 text-xs text-gray-500">
                      <span>8 endpoints</span>
                      <span>•</span>
                      <span>24 test cases</span>
                    </div>
                  </div>
                </div>
                <p className="mt-4 text-sm text-gray-500 text-center">
                  💡 Upload your OpenAPI schema (JSON or YAML) to see it here with generated test cases
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {schemas.map((schema) => (
                <div
                  key={schema.schema_id}
                  className="p-4 bg-white/50 rounded-xl border border-gray-200 hover:shadow-lg transition-all cursor-pointer"
                  onClick={() => navigate(`/schemas/${schema.schema_id}`)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <h4 className="font-semibold text-gray-800 mb-1">{schema.original_filename}</h4>
                      <p className="text-sm text-gray-600 mb-2">{schema.base_url}</p>
                      <div className="flex items-center gap-4 text-xs text-gray-500">
                        <span>{schema.total_endpoints || 0} endpoints</span>
                        <span>•</span>
                        <span>{schema.total_test_cases || 0} test cases</span>
                        <span>•</span>
                        <span>{new Date(schema.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                    <div className="ml-4">
                      <div className="p-2 bg-blue-100 rounded-lg">
                        <FileText className="w-5 h-5 text-blue-600" />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default Dashboard;

