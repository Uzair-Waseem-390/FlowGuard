import { createContext, useContext, useState, useEffect } from 'react';
import api from '../utils/api';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      fetchUser();
    } else {
      setLoading(false);
    }
  }, []);

  const fetchUser = async () => {
    try {
      const response = await api.get('/auth/me');
      setUser(response.data);
    } catch (error) {
      localStorage.removeItem('token');
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    const response = await api.post('/auth/login', { email, password });
    const { access_token } = response.data;
    localStorage.setItem('token', access_token);
    await fetchUser();
    return response.data;
  };

  const signup = async (full_name, email, password, gemini_api_key) => {
    const response = await api.post('/auth/signup/', {
      full_name,
      email,
      password,
      gemini_api_key,
    });
    return response.data;
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
  };

  const updateApiKey = async (gemini_api_key) => {
    // This would need a backend endpoint to update API key
    // For now, we'll just update it in the user object
    // You'll need to create an endpoint like PUT /auth/update-api-key
    try {
      // Assuming you have an endpoint for this
      const response = await api.put('/auth/update-api-key', { gemini_api_key });
      await fetchUser();
      return response.data;
    } catch (error) {
      throw error;
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        signup,
        logout,
        updateApiKey,
        fetchUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

