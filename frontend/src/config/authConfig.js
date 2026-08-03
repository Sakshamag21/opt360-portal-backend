/**
 * OIDC Authentication Configuration for WSO2 Identity Server 5.11
 * 
 * IMPORTANT: Replace the placeholder values with your actual WSO2 configuration
 */

// Support runtime environment variables from window._env_ (for Docker deployments)
const getEnvVar = (key, defaultValue) => {
  return (window._env_ && window._env_[key]) || process.env[key] || defaultValue;
};

const authConfig = {
  // WSO2 Identity Server Authority (Base URL)
  authority: getEnvVar('REACT_APP_WSO2_AUTHORITY', 'https://sso.uidai.net.in/oauth2'),
  
  // Client ID provided by WSO2 for your application
  client_id: getEnvVar('REACT_APP_CLIENT_ID', 'fKaaDJz_1kaCujyYioHzXzwcgjoa'),
  
  // Client Secret (if your application is confidential)
  client_secret: getEnvVar('REACT_APP_CLIENT_SECRET', 'fTAnfnbaNno6G1T1P7s_28XqORsa'),
  
  // Redirect URI after successful authentication
  redirect_uri: getEnvVar('REACT_APP_REDIRECT_URI', 'https://operator360.uidai.net.in/callback'),
  
  // Redirect URI after logout
  post_logout_redirect_uri: getEnvVar('REACT_APP_POST_LOGOUT_REDIRECT_URI', 'https://operator360.uidai.net.in'),
  
  // Response type - using authorization code flow
  response_type: 'code',
  
  // Scopes to request
  scope: 'openid profile email',
  
  // Automatically silent renew the access token
  automaticSilentRenew: false,
  
  // Silent redirect URI
  silent_redirect_uri: getEnvVar('REACT_APP_SILENT_REDIRECT_URI', 'https://operator360.uidai.net.in/silent-renew'),
  
  // Explicit metadata for WSO2 IS
  metadata: {
    issuer: 'https://sso.uidai.net.in/oauth2',
    authorization_endpoint: 'https://sso.uidai.net.in/oauth2/authorize',
    token_endpoint: 'https://sso.uidai.net.in/oauth2/token',
    userinfo_endpoint: 'https://sso.uidai.net.in/oauth2/userinfo',
    end_session_endpoint: 'https://sso.uidai.net.in/oidc/logout',
    jwks_uri: 'https://sso.uidai.net.in/oauth2/jwks',
  },
  
  // PKCE support
  code_challenge_method: null,
  
  // Load user info after authentication
  loadUserInfo: true,
  
  // Filter OIDC protocol claims
  filterProtocolClaims: true,
  
  // Include ID token in silent renew
  includeIdTokenInSilentRenew: false,
};

export default authConfig;
