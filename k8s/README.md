# Kubernetes Deployment

This directory contains Kubernetes manifests for deploying operator360-api using Kustomize.

## Structure

```
k8s/
├── kustomization.yaml    # Kustomize configuration
├── deployment.yaml       # Deployment manifest
├── service.yaml         # Service manifest
└── config/
    └── config.yaml      # Application configuration (mounted as ConfigMap)
```

## Prerequisites

- kubectl configured with cluster access
- kustomize (or kubectl with built-in kustomize)
- Access to harbor-registry-prod.uidai.gov.in

## Configuration

Update `config/config.yaml` with your database credentials and settings before deploying.

## Deployment

### Using kubectl with kustomize

```bash
cd k8s
kubectl apply -k .
```

### Using standalone kustomize

```bash
cd k8s
kustomize build . | kubectl apply -f -
```

## Verify Deployment

```bash
# Check pods
kubectl get pods -n strot-applications -l app=operator360-api

# Check service
kubectl get svc -n strot-applications -l app=operator360-api

# Check logs
kubectl logs -n strot-applications -l app=operator360-api --tail=100

# Port forward for local testing
kubectl port-forward -n strot-applications svc/operator360-api 8000:8000
```

## Update Configuration

To update the configuration:

```bash
# Edit the config file
vim k8s/config/config.yaml

# Apply changes
kubectl apply -k k8s/

# Restart pods to pick up new config
kubectl rollout restart deployment/operator360-api -n strot-applications
```

## Scaling

```bash
# Scale to 3 replicas
kubectl scale deployment/operator360-api -n strot-applications --replicas=3
```

## Delete Deployment

```bash
kubectl delete -k k8s/
```

## Key Features

- **Health Checks**: Liveness and readiness probes configured on `/api/health`
- **Resource Limits**: CPU and memory limits set for stability
- **ConfigMap**: External configuration via ConfigMap
- **Service**: ClusterIP service for internal access
- **Port**: Application runs on port 8000
