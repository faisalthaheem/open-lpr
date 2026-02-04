# Coolify Deployment Guide for Monitoring Stack

This guide explains how to deploy the OpenLPR monitoring stack (Prometheus, Grafana, Blackbox Exporter) on Coolify using custom Docker images with configurations baked in.

## Overview

The monitoring services use custom Docker images that include all necessary configurations, eliminating the need for file mounting from the repository. This approach works seamlessly with Coolify deployments that don't clone the git repository.

## Custom Images

Three custom images are available:

- **ghcr.io/faisalthaheem/open-lpr-prometheus**: Prometheus with OpenLPR configuration
- **ghcr.io/faisalthaheem/open-lpr-grafana**: Grafana with datasource and dashboard provisioning
- **ghcr.io/faisalthaheem/open-lpr-blackbox**: Blackbox Exporter with HTTP probe configuration

## Building Custom Images

### Prerequisites

- Docker installed and running
- Access to the OpenLPR repository

### Build Process

```bash
# Build images locally (test version)
./build-monitoring-images.sh v1.0.0-test false

# Build and push to registry (for production)
./build-monitoring-images.sh v1.0.0 true
```

The script will:
1. Build all three custom images
2. Tag them with both the version number and `latest`
3. Optionally push them to the GitHub Container Registry

## Deploying to Coolify

### Option 1: Using docker-compose.yml

1. **Update Coolify Deployment Configuration**

   Ensure your Coolify deployment uses the custom images. The `docker-compose.yml` has been updated to use the custom images:

   ```yaml
   prometheus:
     image: ghcr.io/faisalthaheem/open-lpr-prometheus:latest
     # ... other configuration ...

   grafana:
     image: ghcr.io/faisalthaheem/open-lpr-grafana:latest
     # ... other configuration ...

   blackbox-exporter:
     image: ghcr.io/faisalthaheem/open-lpr-blackbox:latest
     # ... other configuration ...
   ```

2. **Set Environment Variables**

   Configure the following environment variables in Coolify:

   ```bash
   # Grafana credentials
   GRAFANA_USER=admin
   GRAFANA_PASSWORD=your-secure-password

   # Traefik routing (optional, if using domain names)
   TRAEFIK_HOST=traefik.yourdomain.com
   PROMETHEUS_HOST=prometheus.yourdomain.com
   GRAFANA_HOST=grafana.yourdomain.com
   BLACKBOX_HOST=blackbox.yourdomain.com
   CANARY_HOST=canary.yourdomain.com
   LPR_APP_HOST=lpr.yourdomain.com
   ```

3. **Deploy**

   Redeploy your application in Coolify. The monitoring services will start using the custom images with baked-in configurations.

### Option 2: Individual Service Deployment

If you prefer to deploy monitoring services separately in Coolify:

#### Prometheus Service

1. Create a new service in Coolify
2. Use image: `ghcr.io/faisalthaheem/open-lpr-prometheus:latest`
3. Set environment variables as needed
4. Expose port 9090
5. Add volume: `prometheus_data` mounted to `/prometheus`

#### Grafana Service

1. Create a new service in Coolify
2. Use image: `ghcr.io/faisalthaheem/open-lpr-grafana:latest`
3. Set environment variables:
   - `GF_SECURITY_ADMIN_USER=admin`
   - `GF_SECURITY_ADMIN_PASSWORD=your-secure-password`
   - `GF_USERS_ALLOW_SIGN_UP=false`
4. Expose port 3000
5. Add volume: `grafana_data` mounted to `/var/lib/grafana`

#### Blackbox Exporter Service

1. Create a new service in Coolify
2. Use image: `ghcr.io/faisalthaheem/open-lpr-blackbox:latest`
3. Expose port 9115

## Configuration Changes

When you need to update monitoring configurations:

### Prometheus Configuration

1. Edit `prometheus/prometheus.yml`
2. Rebuild and push the Prometheus image:
   ```bash
   ./build-monitoring-images.sh v1.0.1 true
   ```
3. Update Coolify to use the new image version (e.g., `v1.0.1`)
4. Redeploy

### Grafana Configuration

1. Edit files in `grafana/provisioning/`
2. Rebuild and push the Grafana image:
   ```bash
   ./build-monitoring-images.sh v1.0.1 true
   ```
3. Update Coolify to use the new image version
4. Redeploy

### Blackbox Exporter Configuration

1. Edit `blackbox/blackbox.yml`
2. Rebuild and push the Blackbox image:
   ```bash
   ./build-monitoring-images.sh v1.0.1 true
   ```
3. Update Coolify to use the new image version
4. Redeploy

## Verification

After deployment, verify that the monitoring stack is working:

### Check Prometheus

1. Access Prometheus UI at `http://your-domain:9090` or `http://prometheus.localhost`
2. Go to Status > Targets to verify all targets are up
3. Check that the following targets are being scraped:
   - `prometheus` (self)
   - `lpr-app`
   - `blackbox-exporter`
   - `lpr-canary`

### Check Grafana

1. Access Grafana UI at `http://your-domain:3000` or `http://grafana.localhost`
2. Login with credentials configured in environment variables
3. Verify that:
   - Prometheus datasource is configured (Configuration > Data Sources)
   - Dashboards are provisioned (Dashboards > Manage)

### Check Blackbox Exporter

1. Access Blackbox Exporter at `http://your-domain:9115` or `http://blackbox.localhost`
2. Verify the configuration is loaded
3. Check `/metrics` endpoint for metrics

## Troubleshooting

### Images Not Pulling

If Coolify cannot pull the images:

1. Verify the images are pushed to the registry:
   ```bash
   docker pull ghcr.io/faisalthaheem/open-lpr-prometheus:latest
   docker pull ghcr.io/faisalthaheem/open-lpr-grafana:latest
   docker pull ghcr.io/faisalthaheem/open-lpr-blackbox:latest
   ```

2. Check registry access permissions in Coolify

3. Ensure GitHub Container Registry is accessible from your Coolify server

### Services Not Starting

1. Check Coolify service logs for error messages
2. Verify environment variables are set correctly
3. Ensure volumes are created and accessible
4. Check that ports are not already in use

### Grafana Datasource Not Connecting

1. Verify Prometheus is running and accessible
2. Check network configuration in Coolify
3. Ensure both services are on the same network
4. Verify the Prometheus URL in Grafana datasource configuration

### Metrics Not Appearing

1. Check Prometheus targets are up: `Status > Targets` in Prometheus UI
2. Verify `lpr-app` is exposing metrics at `/metrics`
3. Check network connectivity between services
4. Review Prometheus logs for scraping errors

## CI/CD Integration

To automate image building and pushing, add this to your CI/CD pipeline:

```yaml
# .github/workflows/build-monitoring-images.yml
name: Build Monitoring Images

on:
  push:
    branches: [main]
    paths:
      - 'prometheus/**'
      - 'grafana/**'
      - 'blackbox/**'
      - 'Dockerfile.prometheus'
      - 'Dockerfile.grafana'
      - 'Dockerfile.blackbox'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      
      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v2
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Build Prometheus image
        run: |
          docker build -f Dockerfile.prometheus -t ghcr.io/faisalthaheem/open-lpr-prometheus:${{ github.sha }} .
          docker tag ghcr.io/faisalthaheem/open-lpr-prometheus:${{ github.sha }} ghcr.io/faisalthaheem/open-lpr-prometheus:latest
          docker push ghcr.io/faisalthaheem/open-lpr-prometheus:${{ github.sha }}
          docker push ghcr.io/faisalthaheem/open-lpr-prometheus:latest
      
      - name: Build Grafana image
        run: |
          docker build -f Dockerfile.grafana -t ghcr.io/faisalthaheem/open-lpr-grafana:${{ github.sha }} .
          docker tag ghcr.io/faisalthaheem/open-lpr-grafana:${{ github.sha }} ghcr.io/faisalthaheem/open-lpr-grafana:latest
          docker push ghcr.io/faisalthaheem/open-lpr-grafana:${{ github.sha }}
          docker push ghcr.io/faisalthaheem/open-lpr-grafana:latest
      
      - name: Build Blackbox image
        run: |
          docker build -f Dockerfile.blackbox -t ghcr.io/faisalthaheem/open-lpr-blackbox:${{ github.sha }} .
          docker tag ghcr.io/faisalthaheem/open-lpr-blackbox:${{ github.sha }} ghcr.io/faisalthaheem/open-lpr-blackbox:latest
          docker push ghcr.io/faisalthaheem/open-lpr-blackbox:${{ github.sha }}
          docker push ghcr.io/faisalthaheem/open-lpr-blackbox:latest
```

## Security Considerations

1. **Change Default Passwords**: Always change the default Grafana admin password
2. **Restrict Access**: Use firewalls or Coolify's access controls to restrict access to monitoring endpoints
3. **HTTPS**: Configure HTTPS/TLS for production deployments
4. **Network Isolation**: Keep monitoring services on a private network when possible
5. **Regular Updates**: Keep base images updated by rebuilding custom images regularly

## Performance Considerations

1. **Storage**: Monitor volume usage for Prometheus and Grafana data
2. **Retention**: Adjust Prometheus data retention in `prometheus/prometheus.yml` (default: 200h)
3. **Scrape Intervals**: Balance between metric granularity and performance
4. **Dashboards**: Complex Grafana dashboards can impact performance

## Support

For issues or questions:

1. Check the main OpenLPR documentation
2. Review Coolify documentation for deployment specifics
3. Check logs in Coolify service console
4. Verify configurations against this guide