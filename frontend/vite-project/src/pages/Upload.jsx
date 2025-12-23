import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload as UploadIcon, FileText, Link as LinkIcon, AlertCircle, CheckCircle, ArrowLeft } from 'lucide-react';
import api from '../utils/api';
import ExampleSchema from '../components/ExampleSchema';

const Upload = () => {
  const [baseUrl, setBaseUrl] = useState('');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  const navigate = useNavigate();

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      if (selectedFile.type === 'application/json' || 
          selectedFile.name.endsWith('.yaml') || 
          selectedFile.name.endsWith('.yml')) {
        setFile(selectedFile);
        setMessage({ type: '', text: '' });
      } else {
        setMessage({ type: 'error', text: 'Please upload a JSON or YAML file' });
        setFile(null);
      }
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage({ type: '', text: '' });

    if (!baseUrl || !file) {
      setMessage({ type: 'error', text: 'Please provide both base URL and schema file' });
      return;
    }

    setLoading(true);

    try {
      const formData = new FormData();
      formData.append('base_url', baseUrl);
      formData.append('schema_file', file);

      const response = await api.post('/api/schemas/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setMessage({ type: 'success', text: 'Schema uploaded successfully!' });
      
      setTimeout(() => {
        navigate('/dashboard');
      }, 1500);
    } catch (error) {
      setMessage({
        type: 'error',
        text: error.response?.data?.detail?.message || 
              error.response?.data?.detail || 
              'Failed to upload schema. Please try again.',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 p-6">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => navigate('/dashboard')}
            className="mb-4 flex items-center gap-2 text-gray-600 hover:text-blue-600 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span>Back to Dashboard</span>
          </button>
          <div className="flex items-center gap-3 mb-2">
            <div className="p-3 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl shadow-lg">
              <UploadIcon className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-3xl font-bold gradient-text">Upload Schema</h1>
          </div>
          <p className="text-gray-600">Upload your OpenAPI schema file to start testing</p>
        </div>

        {/* Info Card */}
        <div className="mb-6 glass rounded-2xl p-6 backdrop-blur-xl border border-blue-200 bg-blue-50/50">
          <div className="flex items-start gap-4">
            <div className="p-2 bg-blue-100 rounded-lg">
              <FileText className="w-6 h-6 text-blue-600" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-gray-800 mb-2">What to Upload?</h3>
              <ul className="text-sm text-gray-600 space-y-1">
                <li>✅ <strong>OpenAPI 3.0</strong> schema file (JSON or YAML format)</li>
                <li>✅ Must include <strong>paths</strong> with HTTP methods (GET, POST, etc.)</li>
                <li>✅ Should have <strong>request/response schemas</strong> for POST/PUT endpoints</li>
                <li>✅ Include your API's <strong>base URL</strong> in the form above</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Upload Card */}
        <div className="glass rounded-3xl shadow-2xl p-8 backdrop-blur-xl border border-white/30">
          {/* Message Alert */}
          {message.text && (
            <div
              className={`mb-6 p-4 rounded-xl flex items-center gap-2 ${
                message.type === 'success'
                  ? 'bg-green-50 border border-green-200 text-green-700'
                  : 'bg-red-50 border border-red-200 text-red-700'
              }`}
            >
              {message.type === 'success' ? (
                <CheckCircle className="w-5 h-5" />
              ) : (
                <AlertCircle className="w-5 h-5" />
              )}
              <span className="text-sm">{message.text}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Base URL */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                API Base URL <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <LinkIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="url"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  required
                  className="w-full pl-10 pr-4 py-3 bg-white/70 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                  placeholder="https://api.example.com"
                />
              </div>
              <p className="mt-2 text-xs text-gray-500 flex items-center gap-1">
                <span>💡 Example:</span>
                <code className="bg-gray-100 px-2 py-1 rounded text-gray-700">https://api.example.com</code>
                <span>or</span>
                <code className="bg-gray-100 px-2 py-1 rounded text-gray-700">http://localhost:3000</code>
              </p>
            </div>

            {/* File Upload */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                Schema File (JSON/YAML) <span className="text-red-500">*</span>
              </label>
              <div className="mt-2">
                <label className="flex flex-col items-center justify-center w-full h-48 border-2 border-dashed border-gray-300 rounded-xl cursor-pointer bg-white/50 hover:bg-white/70 transition-all hover:border-blue-500">
                  <div className="flex flex-col items-center justify-center pt-5 pb-6">
                    {file ? (
                      <>
                        <FileText className="w-12 h-12 text-blue-600 mb-2" />
                        <p className="text-sm font-semibold text-gray-700">{file.name}</p>
                        <p className="text-xs text-gray-500 mt-1">
                          {(file.size / 1024).toFixed(2)} KB
                        </p>
                      </>
                    ) : (
                      <>
                        <UploadIcon className="w-12 h-12 text-gray-400 mb-2" />
                        <p className="mb-2 text-sm text-gray-500">
                          <span className="font-semibold">Click to upload</span> or drag and drop
                        </p>
                        <p className="text-xs text-gray-500">JSON or YAML files only</p>
                      </>
                    )}
                  </div>
                  <input
                    type="file"
                    className="hidden"
                    accept=".json,.yaml,.yml"
                    onChange={handleFileChange}
                    required
                  />
                </label>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transform hover:scale-[1.02] transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Uploading...</span>
                </>
              ) : (
                <>
                  <UploadIcon className="w-5 h-5" />
                  <span>Upload Schema</span>
                </>
              )}
            </button>
          </form>

          {/* Example Schema Component */}
          <ExampleSchema />
        </div>
      </div>
    </div>
  );
};

export default Upload;

