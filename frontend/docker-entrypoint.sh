#!/bin/sh
# Runtime environment configuration for React app

# This script generates a runtime config file that can override build-time configs
# Useful for updating redirect URIs based on deployment environment

cat > /usr/share/nginx/html/env-config.js << EOF
window._env_ = {
  REACT_APP_WSO2_AUTHORITY: "${REACT_APP_WSO2_AUTHORITY:-https://sso.uidai.net.in/oauth2/token}",
  REACT_APP_CLIENT_ID: "${REACT_APP_CLIENT_ID:-fKaaDJz_1kaCujyYioHzXzwcgjoa}",
  REACT_APP_CLIENT_SECRET: "${REACT_APP_CLIENT_SECRET:-fTAnfnbaNno6G1T1P7s_28XqORsa}",
  REACT_APP_REDIRECT_URI: "${REACT_APP_REDIRECT_URI:-https://operator360.uidai.net.in/callback}",
  REACT_APP_POST_LOGOUT_REDIRECT_URI: "${REACT_APP_POST_LOGOUT_REDIRECT_URI:-https://operator360.uidai.net.in}",
  REACT_APP_SILENT_REDIRECT_URI: "${REACT_APP_SILENT_REDIRECT_URI:-https://operator360.uidai.net.in/silent-renew}",
  REACT_APP_BACKEND_UPSTREAM: "${REACT_APP_BACKEND_UPSTREAM:-https://operator360.uidai.net.in}"
};
EOF

echo "Runtime environment configuration generated"
cat /usr/share/nginx/html/env-config.js

# Start nginx
exec nginx -g "daemon off;"
