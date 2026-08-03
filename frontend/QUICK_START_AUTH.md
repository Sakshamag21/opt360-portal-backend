# Quick Start Guide - OIDC Authentication

## Installation

1. **Install new dependencies:**
```bash
npm install
```

2. **Create environment file:**
```bash
cp .env.example .env
```

3. **Configure .env with your WSO2 settings:**
```env
REACT_APP_WSO2_AUTHORITY=https://your-wso2-server.com:9443/oauth2/oidcdiscovery
REACT_APP_CLIENT_ID=your_client_id
REACT_APP_REDIRECT_URI=http://localhost:3000/callback
```

4. **Start the application:**
```bash
npm start
```

## What's New

### New Files Created:
- `src/config/authConfig.js` - OIDC configuration
- `src/services/AuthService.js` - Authentication service
- `src/Components/LandingPage.jsx` - Login page
- `src/Components/Callback.jsx` - OAuth callback handler
- `src/Components/ProtectedRoute.jsx` - Route protection
- `src/Components/AuthHeader.jsx` - User info & logout
- `.env.example` - Environment template
- `AUTH_SETUP.md` - Detailed documentation

### Modified Files:
- `package.json` - Added oidc-client-ts and react-router-dom
- `src/App.js` - Added routing configuration
- `src/Components/OperatorAnomalyDashboard.jsx` - Added auth header

## Application Flow

1. User visits `http://localhost:3000/` → **Landing Page**
2. Clicks "Sign In with SSO" → Redirected to **WSO2 Login**
3. Enters AD credentials → WSO2 validates
4. Redirected to `/callback` → **Authorization code exchanged for tokens**
5. Redirected to `/dashboard` → **Operator Dashboard (Protected)**
6. Click user avatar → **Logout option available**

## WSO2 IS Configuration Required

In WSO2 Identity Server Management Console:
1. Create Service Provider: "Operator-360"
2. Configure OAuth/OIDC:
   - **Callback URL:** `http://localhost:3000/callback`
   - **Grant Types:** Authorization Code, Refresh Token
   - **PKCE:** Mandatory
   - **Scopes:** openid profile email

3. Note the Client ID and Client Secret

## Testing

1. Start app: `npm start`
2. Open: `http://localhost:3000`
3. Click "Sign In with SSO"
4. Login with AD credentials
5. You'll be redirected to the dashboard
6. See your user info in the header
7. Click avatar to logout

## Need Help?

See `AUTH_SETUP.md` for detailed documentation.
