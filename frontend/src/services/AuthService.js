import { UserManager, WebStorageStateStore, Log } from 'oidc-client-ts';
import authConfig from '../config/authConfig';

// Enable OIDC logging for debugging (disable in production)
Log.setLogger(console);
Log.setLevel(Log.DEBUG);

class AuthService {
  constructor() {
    // Initialize UserManager with OIDC configuration
    this.userManager = new UserManager({
      ...authConfig,
      stateStore: new WebStorageStateStore({ store: window.sessionStorage })
    });

    // Whitelist of allowed redirect paths to prevent open redirect vulnerability
    this.allowedReturnPaths = [
      '/',
      '/dashboard',
      '/anomalyindicators',
      '/regionevaluation',
      '/viewoperators',
      '/searchpacketdetails',
      '/featureanalysis',
      '/profile',
      '/enrollment-review'
    ];

    // Event listeners
    this.userManager.events.addUserLoaded((user) => {
      console.log('User loaded:', user);
    });

    this.userManager.events.addUserUnloaded(() => {
      console.log('User unloaded');
    });

    this.userManager.events.addAccessTokenExpiring(() => {
      console.log('Access token expiring...');
    });

    this.userManager.events.addAccessTokenExpired(() => {
      console.log('Access token expired');
      this.login();
    });

    this.userManager.events.addSilentRenewError((error) => {
      console.error('Silent renew error:', error);
    });
  }

  /**
   * Starts a local dev session without hitting WSO2 at all.
   * Only callable when built with REACT_APP_ENV=dev, so this code path
   * (and the dummy token it creates) doesn't exist in staging/prod bundles.
   */
  startDevSession() {
    if (process.env.REACT_APP_ENV !== 'dev') {
      throw new Error('startDevSession() is only available in dev builds');
    }

    const nowSeconds = Math.floor(Date.now() / 1000);
    const expiresAt = nowSeconds + 12 * 60 * 60; // 12h, refreshed each landing visit

    const devPayload = {
      sub: 'dev-user',
      preferred_username: 'dev-user',
      name: 'Local Dev User',
      email: 'dev-user@localhost',
      iat: nowSeconds,
      exp: expiresAt
    };
    const dummyJwt = this._buildDummyJWT(devPayload);

    sessionStorage.setItem('access_token', dummyJwt);
    sessionStorage.setItem('id_token', dummyJwt);
    sessionStorage.setItem('token_type', 'Bearer');
    sessionStorage.setItem('expires_at', expiresAt.toString());
    sessionStorage.setItem('refresh_token', dummyJwt);

    const userProfile = {
      ad_id: devPayload.preferred_username,
      username: devPayload.preferred_username,
      email: devPayload.email,
      name: devPayload.name,
      sub: devPayload.sub
    };
    sessionStorage.setItem('user_profile', JSON.stringify(userProfile));

    const oidcUser = {
      access_token: dummyJwt,
      token_type: 'Bearer',
      profile: userProfile,
      expires_at: expiresAt,
      id_token: dummyJwt,
      session_state: null,
      scope: authConfig.scope,
      expired: false,
      scopes: (authConfig.scope || '').split(' ')
    };
    const storageKey = `oidc.user:${authConfig.authority}:${authConfig.client_id}`;
    sessionStorage.setItem(storageKey, JSON.stringify(oidcUser));
  }

  /**
   * Builds a base64url-encoded JWT-shaped string (unsigned) for local dev only.
   */
  _buildDummyJWT(payload) {
    const base64url = (obj) =>
      btoa(JSON.stringify(obj))
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=+$/, '');

    const header = base64url({ alg: 'none', typ: 'JWT' });
    const body = base64url(payload);
    return `${header}.${body}.dev-mode-unsigned`;
  }

  /**
   * Validates a return URL against the whitelist to prevent open redirect attacks
   * @param {string} url - The URL to validate
   * @returns {string} - A safe validated URL from the whitelist, defaults to '/dashboard'
   */
  validateReturnUrl(url) {
    if (!url || typeof url !== 'string') {
      return '/dashboard';
    }

    // Remove any protocol, domain, or query parameters to get just the path
    try {
      const urlObj = new URL(url, window.location.origin);
      const path = urlObj.pathname;
      
      // Check if the path is in the whitelist
      if (this.allowedReturnPaths.includes(path)) {
        return path;
      }
      
      // Check if path starts with any allowed path (for sub-routes)
      const isAllowedSubPath = this.allowedReturnPaths.some(allowedPath => 
        path.startsWith(allowedPath + '/')
      );
      
      if (isAllowedSubPath) {
        return path;
      }
    } catch (e) {
      console.warn('Invalid return URL:', url);
    }
    
    // Default to dashboard if URL is not in whitelist
    console.warn('Return URL not in whitelist, defaulting to /dashboard:', url);
    return '/dashboard';
  }

  /**
   * Initiates the login process by redirecting to WSO2 Identity Server
   */
  async login() {
    try {
      console.log('=== STARTING LOGIN PROCESS ===');
      console.log('Current URL:', window.location.href);
      
      // Store the current path to redirect back after login
      const returnUrl = window.location.pathname;
      sessionStorage.setItem('redirectPath', returnUrl);
      
      console.log('Auth Config:', {
        authority: authConfig.authority,
        client_id: authConfig.client_id,
        redirect_uri: authConfig.redirect_uri,
        response_type: authConfig.response_type,
        scope: authConfig.scope,
        metadata: authConfig.metadata
      });
      
      // Generate cryptographically secure random state
      const array = new Uint8Array(32);
      window.crypto.getRandomValues(array);
      const state = Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
      
      // Store state and return URL
      sessionStorage.setItem('oauth_state', state);
      sessionStorage.setItem('oauth_return_url', returnUrl);
      
      console.log('Generated state:', state);
      
      // Construct authorization URL manually
      const authUrl = new URL(authConfig.metadata.authorization_endpoint);
      authUrl.searchParams.set('client_id', authConfig.client_id);
      authUrl.searchParams.set('redirect_uri', authConfig.redirect_uri);
      authUrl.searchParams.set('response_type', authConfig.response_type);
      authUrl.searchParams.set('scope', authConfig.scope);
      authUrl.searchParams.set('state', state);
      
      console.log('Authorization URL:', authUrl.toString());
      console.log('Redirecting to WSO2...');
      
      // Redirect to WSO2
      window.location.href = authUrl.toString();
      
    } catch (error) {
      console.error('=== ERROR DURING LOGIN REDIRECT ===');
      console.error('Error type:', error.name);
      console.error('Error message:', error.message);
      console.error('Error stack:', error.stack);
      
      alert('Login failed: ' + error.message + '\n\nCheck console for details.');
      throw error;
    }
  }

  /**
   * Handles the callback after successful authentication
   * Extracts authorization code and exchanges it for tokens
   */



  async handleCallback() {
    try {
      console.log('=== HANDLING CALLBACK ===');
      console.log('Current URL:', window.location.href);
      console.log('URL Search Params:', window.location.search);
      
      // Parse URL parameters
      const urlParams = new URLSearchParams(window.location.search);
      const code = urlParams.get('code');
      const state = urlParams.get('state');
      const error = urlParams.get('error');
      const errorDescription = urlParams.get('error_description');
      
      console.log('Received code:', code ? code.substring(0, 20) + '...' : 'Missing');
      console.log('Received state:', state);
      
      // Check for errors from WSO2
      if (error) {
        throw new Error(`WSO2 Error: ${error} - ${errorDescription || 'No description'}`);
      }
      
      // Validate code and state
      if (!code) {
        throw new Error('Authorization code not found in callback URL');
      }
      
      if (!state) {
        throw new Error('State parameter not found in callback URL');
      }
      
      // Validate state matches
      const storedState = sessionStorage.getItem('oauth_state');
      console.log('Stored state:', storedState);
      
      if (state !== storedState) {
        throw new Error('State mismatch - possible CSRF attack');
      }
      
      console.log('State validation successful');
      
      // Exchange authorization code for tokens
      console.log('Exchanging code for tokens...');
      
      const tokenResponse = await fetch(authConfig.metadata.token_endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          grant_type: 'authorization_code',
          code: code,
          redirect_uri: authConfig.redirect_uri,
          client_id: authConfig.client_id,
          client_secret: authConfig.client_secret
        })
      });
      
      if (!tokenResponse.ok) {
        const errorText = await tokenResponse.text();
        console.error('Token exchange failed:', errorText);
        throw new Error(`Token exchange failed: ${tokenResponse.status} ${errorText}`);
      }
      
      const tokenData = await tokenResponse.json();
      console.log('Token exchange successful');
      console.log('Token type:', tokenData.token_type);
      console.log('Expires in:', tokenData.expires_in);
      
      // Store tokens
      sessionStorage.setItem('access_token', tokenData.access_token);
      sessionStorage.setItem('token_type', tokenData.token_type || 'Bearer');
      const expiresAt = Math.floor(Date.now() / 1000) + (tokenData.expires_in || 3600);
      sessionStorage.setItem('expires_at', expiresAt.toString());
      
      if (tokenData.id_token) {
        sessionStorage.setItem('id_token', tokenData.id_token);
      }
      
      if (tokenData.refresh_token) {
        sessionStorage.setItem('refresh_token', tokenData.refresh_token);
      }
      
      // Decode ID token to get user profile (basic JWT decode)
      let userProfile = {};
      if (tokenData.id_token) {
        try {
          const base64Url = tokenData.id_token.split('.')[1];
          const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
          const jsonPayload = decodeURIComponent(atob(base64).split('').map(c => 
            '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)
          ).join(''));
          
          const idTokenPayload = JSON.parse(jsonPayload);
          console.log('ID Token payload:', idTokenPayload);
          
          userProfile = {
            ad_id: idTokenPayload.preferred_username || idTokenPayload.sub || idTokenPayload.email,
            username: idTokenPayload.preferred_username || idTokenPayload.name || idTokenPayload.email,
            email: idTokenPayload.email,
            name: idTokenPayload.name,
            sub: idTokenPayload.sub,
            ...idTokenPayload
          };
        } catch (decodeError) {
          console.error('Error decoding ID token:', decodeError);
        }
      }
      
      sessionStorage.setItem('user_profile', JSON.stringify(userProfile));
      console.log('User profile stored:', userProfile);
      
      // Store user data in OIDC client format for compatibility with UserManager
      const oidcUser = {
        access_token: tokenData.access_token,
        token_type: tokenData.token_type || 'Bearer',
        profile: userProfile,
        expires_at: expiresAt,
        id_token: tokenData.id_token,
        session_state: null,
        scope: authConfig.scope,
        expired: false,
        scopes: authConfig.scope.split(' ')
      };
      
      // Store in the format UserManager expects
      const storageKey = `oidc.user:${authConfig.authority}:${authConfig.client_id}`;
      sessionStorage.setItem(storageKey, JSON.stringify(oidcUser));
      console.log('OIDC user stored with key:', storageKey);
      
      // Clean up OAuth state
      sessionStorage.removeItem('oauth_state');
      
      // Get and validate return URL against whitelist
      const unsafeReturnUrl = sessionStorage.getItem('oauth_return_url');
      const returnUrl = this.validateReturnUrl(unsafeReturnUrl);
      sessionStorage.removeItem('oauth_return_url');
      
      console.log('=== AUTHENTICATION SUCCESSFUL ===');
      console.log('User AD ID:', userProfile.ad_id);
      console.log('Username:', userProfile.username);
      console.log('Return URL:', returnUrl);
      
      return {
        user: {
          access_token: tokenData.access_token,
          token_type: tokenData.token_type,
          expires_at: expiresAt,
          profile: userProfile
        },
        returnUrl
      };
    } catch (error) {
      console.error('Error handling authentication callback:', error);
      // Clean up on error
      sessionStorage.removeItem('oauth_state');
      sessionStorage.removeItem('oauth_return_url');
      throw error;
    }
  }




  /**
   * Logs out the user and redirects to WSO2 logout endpoint
   */
  async logout() {
    try {
      // Clear session storage tokens
      sessionStorage.removeItem('access_token');
      sessionStorage.removeItem('token_type');
      sessionStorage.removeItem('expires_at');
      sessionStorage.removeItem('user_profile');
      
      await this.userManager.signoutRedirect();
    } catch (error) {
      console.error('Error during logout:', error);
      throw error;
    }
  }

  /**
   * Silently renews the access token
   */
  async renewToken() {
    try {
      const user = await this.userManager.signinSilent();
      
      // Update access token in session storage
      if (user.access_token) {
        sessionStorage.setItem('access_token', user.access_token);
        sessionStorage.setItem('token_type', user.token_type || 'Bearer');
        sessionStorage.setItem('expires_at', user.expires_at);
        
        // Store user profile with ad_id
        const userProfile = {
          ad_id: user.profile.preferred_username || user.profile.sub || user.profile.email,
          username: user.profile.preferred_username || user.profile.name || user.profile.email,
          email: user.profile.email,
          name: user.profile.name,
          sub: user.profile.sub,
          ...user.profile
        };
        sessionStorage.setItem('user_profile', JSON.stringify(userProfile));
      }
      
      return user;
    } catch (error) {
      console.error('Error renewing token:', error);
      throw error;
    }
  }

  /**
   * Gets the current authenticated user
   */
  async getUser() {
    try {
      const user = await this.userManager.getUser();
      return user;
    } catch (error) {
      console.error('Error getting user:', error);
      return null;
    }
  }

  /**
   * Checks if user is authenticated
   */
  async isAuthenticated() {
    try {
      const user = await this.getUser();
      return user !== null && !user.expired;
    } catch (error) {
      return false;
    }
  }

  /**
   * Gets the access token
   */
  async getAccessToken() {
    try {
      // Try to get from session storage first
      const storedToken = sessionStorage.getItem('access_token');
      if (storedToken) {
        const expiresAt = parseInt(sessionStorage.getItem('expires_at'));
        const now = Math.floor(Date.now() / 1000);
        
        // Check if token is still valid
        if (expiresAt && expiresAt > now) {
          return storedToken;
        }
      }
      
      // If not in session storage or expired, get from UserManager
      const user = await this.getUser();
      if (user?.access_token) {
        // Update session storage
        sessionStorage.setItem('access_token', user.access_token);
        sessionStorage.setItem('token_type', user.token_type || 'Bearer');
        sessionStorage.setItem('expires_at', user.expires_at);
        
        // Store user profile with ad_id
        const userProfile = {
          ad_id: user.profile.preferred_username || user.profile.sub || user.profile.email,
          username: user.profile.preferred_username || user.profile.name || user.profile.email,
          email: user.profile.email,
          name: user.profile.name,
          sub: user.profile.sub,
          ...user.profile
        };
        sessionStorage.setItem('user_profile', JSON.stringify(userProfile));
        
        return user.access_token;
      }
      
      return null;
    } catch (error) {
      console.error('Error getting access token:', error);
      return null;
    }
  }

  /**
   * Gets the ID token
   */
  async getIdToken() {
    try {
      const user = await this.getUser();
      return user?.id_token || null;
    } catch (error) {
      console.error('Error getting ID token:', error);
      return null;
    }
  }


  /**
   * Gets user profile information
   */
  async getUserProfile() {
    try {
      const user = await this.getUser();
      return user?.profile || null;
    } catch (error) {
      console.error('Error getting user profile:', error);
      return null;
    }
  }

  /**
   * Removes user from storage (for silent logout)
   */
  async removeUser() {
    try {
      await this.userManager.removeUser();
    } catch (error) {
      console.error('Error removing user:', error);
    }
  }

  /**
   * Logs out the user by clearing session and redirecting to WSO2 logout endpoint
   */
  async logout() {
    try {
      console.log('=== STARTING LOGOUT PROCESS ===');
      
      // Get the ID token for WSO2 logout (required by some IdP implementations)
      const idToken = sessionStorage.getItem('id_token');
      
      // Clear all session storage
      sessionStorage.removeItem('access_token');
      sessionStorage.removeItem('id_token');
      sessionStorage.removeItem('refresh_token');
      sessionStorage.removeItem('token_type');
      sessionStorage.removeItem('expires_at');
      sessionStorage.removeItem('user_profile');
      sessionStorage.removeItem('oauth_state');
      sessionStorage.removeItem('oauth_return_url');
      sessionStorage.removeItem('redirectPath');
      
      console.log('Session storage cleared');
      
      // Remove user from OIDC UserManager
      await this.userManager.removeUser();
      
      // Construct WSO2 logout URL
      const logoutUrl = new URL(authConfig.metadata.end_session_endpoint);
      
      // Add parameters for proper WSO2 logout
      if (idToken) {
        logoutUrl.searchParams.set('id_token_hint', idToken);
      }
      logoutUrl.searchParams.set('post_logout_redirect_uri', authConfig.post_logout_redirect_uri);
      
      console.log('Redirecting to WSO2 logout:', logoutUrl.toString());
      
      // Redirect to WSO2 logout endpoint
      window.location.href = logoutUrl.toString();
      
    } catch (error) {
      console.error('=== ERROR DURING LOGOUT ===');
      console.error('Error:', error);
      
      // Even if there's an error, try to clear session and redirect to home
      sessionStorage.clear();
      window.location.href = authConfig.post_logout_redirect_uri;
    }
  }
}

// Create a singleton instance
const authService = new AuthService();

export default authService;


