import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, CheckCircle, AlertCircle } from 'lucide-react';
import authService from '../services/AuthService';

const Callback = () => {
  const navigate = useNavigate();
  const [status, setStatus] = useState('processing'); // processing, success, error
  const [message, setMessage] = useState('Processing authentication...');
  const [userInfo, setUserInfo] = useState(null);

  useEffect(() => {
    handleAuthCallback();
  }, []);

  const handleAuthCallback = async () => {
    try {
      console.log('=== CALLBACK COMPONENT MOUNTED ===');
      console.log('Current URL:', window.location.href);
      console.log('Search params:', window.location.search);
      console.log('Hash:', window.location.hash);
      
      setStatus('processing');
      setMessage('Validating authorization code...');

      console.log('Calling authService.handleCallback()...');
      
      // Handle the callback and exchange authorization code for tokens
      const result = await authService.handleCallback();
      
      console.log('handleCallback completed successfully');
      console.log('Result:', result);
      
      if (result && result.user) {
        setStatus('success');
        setMessage('Authentication successful! Redirecting...');
        setUserInfo({
          name: result.user.profile.name || result.user.profile.username || result.user.profile.ad_id || 'User',
          email: result.user.profile.email,
          userId: result.user.profile.sub
        });

        console.log('Authentication successful - redirecting to:', result.returnUrl);

        // Redirect to returnUrl from authentication result
        setTimeout(() => {
          console.log('Navigating to:', result.returnUrl);
          navigate(result.returnUrl, { replace: true });
        }, 1000);
      } else {
        throw new Error('No user data received');
      }
    } catch (error) {
      console.error('=== AUTHENTICATION CALLBACK ERROR ===');
      console.error('Error:', error);
      console.error('Error message:', error.message);
      console.error('Error stack:', error.stack);
      
      setStatus('error');
      setMessage(error.message || 'Authentication failed. Please try again.');
      
      // Redirect to landing page after showing error
      setTimeout(() => {
        console.log('Redirecting to landing page due to error');
        navigate('/', { replace: true });
      }, 3000);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#d2c5e7] via-[#e8dff2] to-white flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-md w-full border-2 border-[#d2c5e7]">
        <div className="text-center">
          {/* Icon */}
          <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-[#9b7bb5] to-[#d2c5e7] rounded-full mb-6">
            {status === 'processing' && (
              <div className="relative">
                <Shield className="w-10 h-10 text-white" />
                <svg className="absolute top-0 left-0 w-20 h-20 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="white" strokeWidth="2"></circle>
                  <path className="opacity-75" fill="white" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>
            )}
            {status === 'success' && (
              <CheckCircle className="w-10 h-10 text-white animate-pulse" />
            )}
            {status === 'error' && (
              <AlertCircle className="w-10 h-10 text-white" />
            )}
          </div>

          {/* Status Message */}
          <h2 className={`text-2xl font-bold mb-3 ${
            status === 'error' ? 'text-red-600' : 'text-gray-900'
          }`}>
            {status === 'processing' && 'Authenticating...'}
            {status === 'success' && 'Welcome Back!'}
            {status === 'error' && 'Authentication Failed'}
          </h2>

          <p className="text-gray-600 mb-6">{message}</p>

          {/* User Info on Success */}
          {status === 'success' && userInfo && (
            <div className="bg-gradient-to-br from-[#f5f2f8] to-[#e8dff2] rounded-xl p-4 mb-6 border border-[#d2c5e7]">
              <p className="text-sm text-gray-600 mb-1">Signed in as</p>
              <p className="font-bold text-gray-900">{userInfo.name}</p>
              {userInfo.email && (
                <p className="text-sm text-gray-600 mt-1">{userInfo.email}</p>
              )}
            </div>
          )}

          {/* Loading Indicator */}
          {status === 'processing' && (
            <div className="space-y-3">
              <div className="flex items-center justify-center gap-2">
                <div className="w-2 h-2 bg-[#9b7bb5] rounded-full animate-bounce" style={{ animationDelay: '0s' }}></div>
                <div className="w-2 h-2 bg-[#9b7bb5] rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-[#9b7bb5] rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
              <p className="text-xs text-gray-500">
                Exchanging authorization code for access tokens...
              </p>
            </div>
          )}

          {/* Success Animation */}
          {status === 'success' && (
            <div className="flex items-center justify-center gap-2 text-green-600">
              <CheckCircle className="w-5 h-5" />
              <span className="text-sm font-medium">Redirecting to dashboard...</span>
            </div>
          )}

          {/* Error Message */}
          {status === 'error' && (
            <div className="mt-6">
              <button
                onClick={() => navigate('/', { replace: true })}
                className="px-6 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg font-semibold transition-all duration-300"
              >
                Return to Sign In
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="mt-8 pt-6 border-t border-gray-200 text-center">
          <p className="text-xs text-gray-500">
            Secured by WSO2 Identity Server • OIDC Protocol
          </p>
        </div>
      </div>
    </div>
  );
};

export default Callback;
