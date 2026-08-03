# WSO2 Authentication Deployment Guide

## Configuration Summary

The application is now configured to work with WSO2 Identity Server with the following credentials:

- **Authority**: https://sso.uidai.net.in/oauth2/token/.well-known/openid-configuration
- **Client ID**: 9HGuTetQjRjxkx1vHmoP1v0fXm8a
- **Client Secret**: RlsK9p2f4kJ_iKBZLSgiBYuIKjQa

## For Kubernetes Deployment

Update your `deployment.yaml` to include environment variables for production URLs:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: operator-360-ui 
  namespace: strot-applications
spec:
  template:
    spec:
      containers:
      - name: operator-360-ui
        image: "harbor-registry-non-prod.uidai.gov.in/data-platform/operator-360-ui:0.1.2-SNAPSHOT"
        env:
        # WSO2 Configuration
        - name: REACT_APP_WSO2_AUTHORITY
          value: "https://sso.uidai.net.in/oauth2/token/.well-known/openid-configuration"
        - name: REACT_APP_CLIENT_ID
          value: "9HGuTetQjRjxkx1vHmoP1v0fXm8a"
        - name: REACT_APP_CLIENT_SECRET
          valueFrom:
            secretKeyRef:
              name: wso2-credentials
              key: client-secret
        # Update these with your actual deployment URLs
        - name: REACT_APP_REDIRECT_URI
          value: "https://your-domain.com/callback"
        - name: REACT_APP_POST_LOGOUT_REDIRECT_URI
          value: "https://your-domain.com"
        - name: REACT_APP_SILENT_REDIRECT_URI
          value: "https://your-domain.com/silent-renew"
```

## Create Kubernetes Secret for Client Secret

```bash
kubectl create secret generic wso2-credentials \
  --from-literal=client-secret='RlsK9p2f4kJ_iKBZLSgiBYuIKjQa' \
  -n strot-applications
```

## Docker Build with Custom URLs

Build with custom environment variables:

```bash
docker build \
  --build-arg REACT_APP_REDIRECT_URI=https://your-domain.com/callback \
  --build-arg REACT_APP_POST_LOGOUT_REDIRECT_URI=https://your-domain.com \
  --build-arg REACT_APP_SILENT_REDIRECT_URI=https://your-domain.com/silent-renew \
  -t operator-360-ui:0.1.2-SNAPSHOT .
```

## Local Development

For local development, the `.env` file is already configured with localhost URLs.

Start the development server:
```bash
npm start
```

## Important Notes

1. **Update Redirect URIs**: Make sure to register your production URLs in WSO2 Identity Server
2. **HTTPS Required**: WSO2 typically requires HTTPS for production deployments
3. **CORS Configuration**: Ensure WSO2 allows CORS from your application domain
4. **Client Secret**: Store client secret securely using Kubernetes secrets in production
