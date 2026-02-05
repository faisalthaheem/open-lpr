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

   # Service Ports (optional - defaults will be used if not set)
   # NOTE: For Coolify deployment, DO NOT set TRAEFIK_HTTP_PORT to avoid port conflicts
   # Leave these unset to use default ports, or customize if needed
   LPR_APP_PORT=8000
   PROMETHEUS_PORT=9090
   GRAFANA_PORT=3000
   BLACKBOX_PORT=9115
   CANARY_PORT=9100
   ```

3. **Deploy**

   Redeploy your application in Coolify. The monitoring services will start using the custom images with baked-in configurations.

### Important: Traefik Configuration for Coolify

**By default, Coolify provides its own reverse proxy and routing.** To avoid port conflicts:

1. **DO NOT set** `TRAEFIK_HTTP_PORT` environment variable in Coolify
2. **DO NOT set** `TRAEFIK_DASHBOARD_PORT` environment variable in Coolify

When these variables are empty/not set:
- Traefik container will start but won't expose ports (80, 8080)
- No port conflicts with Coolify's services
- Services are accessible directly via their assigned ports

If you DO want to use Traefik (for local development or specific use cases):
```bash
# Only set these if NOT using Coolify
TRAEFIK_HTTP_PORT=80
TRAEFIK_DASHBOARD_PORT=8080
```

### Customizing Service Ports

All service ports are configurable via environment variables. Use this to avoid conflicts:

```bash
# Example: Use alternative ports to avoid conflicts
LPR_APP_PORT=8080
PROMETHEUS_PORT=9091
GRAFANA_PORT=3001
BLACKBOX_PORT=9116
CANARY_PORT=9101
```

### Option 2: Individual Service Deployment

If you prefer to deploy monitoring services separately in Coolify:

#### Prometheus Service

1. Create a new service in Coolify
2. Use image: `ghcr.io/faisalthaheem/open-lpr-prometheus:latest`
3. Set environment variables as needed
4. Expose port (default: 9090, or set `PROMETHEUS_PORT`)
5. Add volume: `prometheus_data` mounted to `/prometheus`

#### Grafana Service

1. Create a new service in Coolify
2. Use image: `ghcr.io/faisalthaheem/open-lpr-grafana:latest`
3. Set environment variables:
   - `GF_SECURITY_ADMIN_USER=admin`
   - `GF_SECURITY_ADMIN_PASSWORD=your-secure-password`
   - `GF_USERS_ALLOW_SIGN_UP=false`
   - `GRAFANA_PORT=3000` (optional, default is 3000)
4. Expose port (default: 3000, or set `GRAFANA_PORT`)
5. Add volume: `grafana_data` mounted to `/var/lib/grafana`

#### Blackbox Exporter Service

1. Create a new service in Coolify
2. Use image: `ghcr.io/faisalthaheem/open-lpr-blackbox:latest`
3. Set environment variable `BLACKBOX_PORT=9115` (optional, default is 9115)
4. Expose port (default: 9115, or set `BLACKBOX_PORT`)

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

1. Access Prometheus UI at:
   - `http://your-domain:9090` (or configured `PROMETHEUS_PORT`)
   - `http://prometheus.localhost` (if using Traefik)
2. Go to Status > Targets to verify all targets are up
3. Check that the following targets are being scraped:
   - `prometheus` (self)
   - `lpr-app`
   - `blackbox-exporter`
   - `lpr-canary`

### Check Grafana

1. Access Grafana UI at:
   - `http://your-domain:3000` (or configured `GRAFANA_PORT`)
   - `http://grafana.localhost` (if using Traefik)
2. Login with credentials configured in environment variables
3. Verify that:
   - Prometheus datasource is configured (Configuration > Data Sources)
   - Dashboards are provisioned (Dashboards > Manage)

### Check Blackbox Exporter

1. Access Blackbox Exporter at:
   - `http://your-domain:9115` (or configured `BLACKBOX_PORT`)
   - `http://blackbox.localhost` (if using Traefik)
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
5. **If Traefik fails with "port is already allocated":**
   - Ensure `TRAEFIK_HTTP_PORT` and `TRAEFIK_DASHBOARD_PORT` are NOT set
   - Coolify may already be using ports 80 and 8080
   - Traefik will work fine without exposed ports (internal routing only)

### Port Conflicts

If you encounter port conflicts:

1. Check which ports are already in use:
   ```bash
   sudo netstat -tulpn | grep LISTEN
   ```

2. Use alternative ports by setting environment variables:
   ```bash
   LPR_APP_PORT=8080
   PROMETHEUS_PORT=9091
   GRAFANA_PORT=3001
   BLACKBOX_PORT=9116
   CANARY_PORT=9101
   ```

3. For Coolify deployments, ensure Traefik ports are NOT set:
   - Leave `TRAEFIK_HTTP_PORT` empty
   - Leave `TRAEFIK_DASHBOARD_PORT` empty

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

To automate image building and pushing, use the included GitHub Actions workflow:

`.github/workflows/build-monitoring-images.yml` - This workflow automatically builds and pushes all three monitoring images when:
- Changes are pushed to `main` branch
- Monitoring-related files are modified (prometheus/, grafana/, blackbox/, or Dockerfiles)

The workflow builds images for both `linux/amd64` and `linux/arm64` architectures and supports:
- Automatic tagging (latest, branch names, semantic versioning)
- GitHub Container Registry authentication
- Build caching for faster builds

To manually trigger the workflow, go to Actions tab in GitHub and select "Build and Publish Monitoring Images" > Run workflow.

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