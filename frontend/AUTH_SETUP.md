# OIDC Authentication Setup Guide

## Overview
This application uses **WSO2 Identity Server 5.11** with **OIDC (OpenID Connect)** protocol for authentication and authorization using Active Directory credentials.

## Prerequisites
1. WSO2 Identity Server 5.11 configured and running
2. A registered OAuth 2.0 / OIDC application in WSO2 IS
3. Client ID and Client Secret (if applicable)
4. Configured redirect URIs in WSO2 IS

## Installation Steps

### 1. Install Dependencies
```bash
npm install
```

This will install:
- `oidc-client-ts` - OIDC client library
- `react-router-dom` - For routing

### 2. Configure Environment Variables

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Update `.env` with your WSO2 IS configuration:

```env
# WSO2 Identity Server Base URL
REACT_APP_WSO2_AUTHORITY=https://your-wso2-server.com:9443/oauth2/oidcdiscovery

# Your OAuth Client ID
REACT_APP_CLIENT_ID=your_client_id_here

# Client Secret (if using confidential client)
REACT_APP_CLIENT_SECRET=your_client_secret_here

# Redirect URIs
REACT_APP_REDIRECT_URI=http://localhost:3000/callback
REACT_APP_POST_LOGOUT_REDIRECT_URI=http://localhost:3000
```

### 3. Configure WSO2 Identity Server

#### Register OAuth 2.0 Application:
1. Log in to WSO2 IS Management Console (`https://your-wso2-server:9443/carbon`)
2. Navigate to: **Main** → **Service Providers** → **Add**
3. Create a new Service Provider (e.g., "Operator-360")
4. Expand **Inbound Authentication Configuration** → **OAuth/OpenID Connect Configuration**
5. Click **Configure**

#### OAuth Configuration Settings:
```
Callback URL: http://localhost:3000/callback
Allowed Grant Types: 
  ✓ Authorization Code
  ✓ Refresh Token
  
PKCE: Mandatory (recommended for security)

Scopes: openid profile email

Access Token Type: JWT (optional)
```

6. Save and note down the **Client ID** and **Client Secret**

### 4. Update Allowed Redirect URIs

In WSO2 IS, configure these redirect URIs:
- `http://localhost:3000/callback` (for development)
- `http://localhost:3000/silent-renew` (for token renewal)
- Add production URLs when deploying

## Application Flow

### 1. Landing Page
- User visits the application at `/`
- Sees the Landing Page with "Sign In" button

### 2. Authentication
- User clicks "Sign In with SSO"
- Redirected to WSO2 IS login page
- User enters AD credentials (username/password)
- WSO2 IS validates credentials against Active Directory

### 3. Authorization Code Flow
- Upon successful login, WSO2 IS redirects to `/callback` with authorization code
- Application exchanges authorization code for access token and ID token
- Tokens are stored in session storage

### 4. Dashboard Access
- User is redirected to `/dashboard`
- OperatorAnomalyDashboard component is displayed
- Auth header shows user information

### 5. Protected Routes
- All routes under `/dashboard` are protected
- Unauthenticated users are redirected to Landing Page
- Token is automatically renewed before expiration

### 6. Logout
- User clicks logout in the header dropdown
- Tokens are cleared
- User is redirected to WSO2 IS logout endpoint
- Finally redirected back to Landing Page

## File Structure

```
src/
├── config/
│   └── authConfig.js          # OIDC configuration
├── services/
│   └── AuthService.js         # Authentication service
├── Components/
│   ├── LandingPage.jsx        # Login page with Sign In button
│   ├── Callback.jsx           # Handles OAuth callback
│   ├── ProtectedRoute.jsx     # Route protection wrapper
│   ├── AuthHeader.jsx         # Header with user info and logout
│   └── OperatorAnomalyDashboard.jsx  # Main dashboard
├── App.js                     # Routing configuration
└── index.js                   # App entry point
```

## Usage

### Start Development Server
```bash
npm start
```

Access at: http://localhost:3000

### Routes
- `/` - Landing page (public)
- `/callback` - OAuth callback handler (public)
- `/dashboard` - Operator dashboard (protected)

## Debugging

Enable OIDC debugging by checking browser console:
- Authentication events
- Token information (without exposing secrets)
- User profile data
- Error messages

## Security Features

✅ **Authorization Code Flow** - Most secure OAuth flow
✅ **PKCE (Proof Key for Code Exchange)** - Protection against authorization code interception
✅ **State Parameter** - CSRF protection
✅ **Token Storage** - Session storage (cleared on tab close)
✅ **Automatic Token Renewal** - Silent token refresh before expiration
✅ **Secure Logout** - Clears tokens and redirects to IdP

## Production Deployment

### 1. Update Environment Variables
```env
REACT_APP_WSO2_AUTHORITY=https://wso2.company.com:9443/oauth2/oidcdiscovery
REACT_APP_CLIENT_ID=production_client_id
REACT_APP_REDIRECT_URI=https://operator360.company.com/callback
REACT_APP_POST_LOGOUT_REDIRECT_URI=https://operator360.company.com
```

### 2. Update WSO2 IS
- Add production callback URLs
- Configure CORS if needed
- Update allowed origins

### 3. Build Application
```bash
npm run build
```

### 4. Deploy
Deploy the `build` folder to your web server (nginx, Apache, etc.)

## Troubleshooting

### Issue: "Authentication failed for 'https://bitbucket.uidai.net.in/...'"
This is a Git authentication issue, not related to OIDC. See separate Git authentication guide.

### Issue: CORS Errors
Configure CORS in WSO2 IS:
```
identity.xml → CORS → AllowedOrigins
Add: http://localhost:3000
```

### Issue: Token Validation Failed
- Check WSO2 IS clock synchronization
- Verify JWT signature algorithm matches
- Ensure client ID is correct

### Issue: Redirect Loop
- Verify callback URL exactly matches WSO2 IS configuration
- Check browser console for errors
- Clear session storage and try again

## API Integration

To use access tokens for API calls:

```javascript
import authService from './services/AuthService';

const fetchData = async () => {
  const accessToken = await authService.getAccessToken();
  
  const response = await fetch('https://api.example.com/data', {
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    }
  });
  
  return response.json();
};
```

## Support

For WSO2 IS configuration issues, refer to:
- [WSO2 IS 5.11 Documentation](https://is.docs.wso2.com/en/5.11.0/)
- [OAuth 2.0 / OIDC Configuration Guide](https://is.docs.wso2.com/en/5.11.0/guides/login/oauth-app-config-advanced/)

## License

This authentication implementation follows the main project license.
