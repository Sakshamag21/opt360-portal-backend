/**
 * API Configuration
 * Supports both build-time (process.env) and runtime (window._env_) configuration
 */

const getApiBaseUrl = () => {
  // Try runtime config first (for Docker/production)
  if (window._env_ && window._env_.REACT_APP_BACKEND_UPSTREAM) {
    console.log("API Base URL from runtime config:", window._env_.REACT_APP_BACKEND_UPSTREAM);
    return window._env_.REACT_APP_BACKEND_UPSTREAM;
  }
  
  // Fall back to build-time env variable
  if (process.env.REACT_APP_BACKEND_UPSTREAM) {
    console.log("API Base URL from build-time env:", process.env.REACT_APP_BACKEND_UPSTREAM);
    return process.env.REACT_APP_BACKEND_UPSTREAM;
  }
  console.log("API Base URL not set in env variables.");
  
  return 'https://operator360.uidai.net.in';
};

export const API_BASE_URL = getApiBaseUrl();

export const getAuthHeaders = () => ({
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${sessionStorage.getItem('id_token')}`
});

export default {
  baseUrl: API_BASE_URL
};
