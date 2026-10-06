# Docker Compose Profiles Guide

This document explains the different Docker Compose profiles available for deploying OpenLPR.

## Overview

OpenLPR uses Docker Compose profiles to allow flexible deployment scenarios. Each profile groups related services together.

## Available Profiles

### `core` - Core Application and Monitoring

**Services included:**
- `lpr-app` - Main OpenLPR Django application
- `prometheus` - Metrics collection and storage
- `grafana` - Metrics visualization and dashboards
- `blackbox-exporter` - HTTP probe for health checking
- `lpr-canary` - Canary tests and synthetic monitoring

**When to use:**
- Production deployments
- Development with monitoring
- When you don't need a reverse proxy
- Coolify deployments (which provide their own routing)

**Deployment:**
```bash
docker compose --profile core up -d
```

**Access points:**
- OpenLPR: http://localhost:8000
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (default: admin/admin)
- Blackbox Exporter: http://localhost:9115
- Canary Metrics: http://localhost:9100/metrics

**Network Communication:**
All services in the `core` profile communicate via the `openlpr-network` bridge network, regardless of whether a reverse proxy is used. Services use internal DNS names (e.g., `lpr-app`, `prometheus`) to communicate with each other.

### `proxy` - Reverse Proxy (Traefik)

**Services included:**
- `traefik` - Modern HTTP reverse proxy and load balancer

**When to use:**
- Local development with domain-based routing
- When you need a reverse proxy but not using Coolify
- To access services via friendly URLs (e.g., `lpr.localhost`)
- To enable HTTPS/TLS termination

**Deployment:**
```bash
# Deploy core services + proxy
docker compose --profile core --profile proxy up -d

# Or add proxy to existing core deployment
docker compose --profile proxy up -d
```

**Access points:**
- OpenLPR: http://lpr.localhost
- Prometheus: http://prometheus.localhost
- Grafana: http://grafana.localhost
- Blackbox Exporter: http://blackbox.localhost
- Canary: http://canary.localhost
- Traefik Dashboard: http://traefik.localhost (or `TRAEFIK_HOST`)

**Note:** Traefik uses random ports by default (e.g., 32768, 32769). Set `TRAEFIK_HTTP_PORT` and `TRAEFIK_DASHBOARD_PORT` to use specific ports (e.g., 80, 8080).

### `cpu` - CPU Inference

**Services included:**
- `llamacpp-cpu` - Llama.cpp server for CPU inference

**When to use:**
- Systems without GPU acceleration
- Development and testing
- When model inference performance is not critical

**Deployment:**
```bash
docker compose --profile core --profile cpu up -d
```

**Configuration:**
See `.env.llamacpp` for model configuration.

### `amd-vulkan` - AMD GPU Inference

**Services included:**
- `llamacpp-amd-vulkan` - Llama.cpp server for AMD GPU inference (Vulkan)

**When to use:**
- Systems with AMD GPUs supporting Vulkan
- Production deployments requiring faster inference

**Requirements:**
- AMD GPU with Vulkan support
- GPU drivers installed
- `/dev/kfd` and `/dev/dri` device access

**Deployment:**
```bash
docker compose --profile core --profile amd-vulkan up -d
```

### `nvidia-cuda` - NVIDIA GPU Inference

**Services included:**
- `llamacpp-nvidia-cuda` - Llama.cpp server for NVIDIA GPU inference (CUDA)

**When to use:**
- Systems with NVIDIA GPUs
- Production deployments requiring fastest inference
- When using NVIDIA CUDA ecosystem

**Requirements:**
- NVIDIA GPU with CUDA support
- NVIDIA Container Toolkit installed
- GPU drivers installed

**Deployment:**
```bash
docker compose --profile core --profile nvidia-cuda up -d
```

## Profile Combinations

### Development Setup (No Proxy)
```bash
docker compose --profile core up -d
```
Access services directly via ports.

### Development Setup (With Proxy)
```bash
docker compose --profile core --profile proxy up -d
```
Access services via domain names.

### Production with CPU Inference
```bash
docker compose --profile core --profile cpu up -d
```

### Production with NVIDIA GPU
```bash
docker compose --profile core --profile nvidia-cuda up -d
```

### Production with AMD GPU
```bash
docker compose --profile core --profile amd-vulkan up -d
```

## Environment Variables

### Service Ports

All service ports are configurable via environment variables:

```bash
# Core services
LPR_APP_PORT=8000
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
BLACKBOX_PORT=9115
CANARY_PORT=9100

# Proxy (only when using proxy profile)
TRAEFIK_HTTP_PORT=80          # Leave unset for Coolify
TRAEFIK_DASHBOARD_PORT=8080   # Leave unset for Coolify
```

### Proxy Host Names

When using the `proxy` profile, you can customize domain names:

```bash
TRAEFIK_HOST=traefik.yourdomain.com
PROMETHEUS_HOST=prometheus.yourdomain.com
GRAFANA_HOST=grafana.yourdomain.com
BLACKBOX_HOST=blackbox.yourdomain.com
CANARY_HOST=canary.yourdomain.com
LPR_APP_HOST=lpr.yourdomain.com
```

## Coolify Deployment

For Coolify deployments:

1. **Use the `core` profile** - don't include `proxy`
2. **DO NOT set** `TRAEFIK_HTTP_PORT` or `TRAEFIK_DASHBOARD_PORT`
3. Coolify provides its own reverse proxy and routing
4. Services communicate via internal Docker network
5. Access services via Coolify's configured domains

```bash
# Coolify deployment command
docker compose --profile core up -d
```

## Managing Profiles

### View running services
```bash
docker compose ps
```

### Stop specific profile
```bash
docker compose --profile proxy down
```

### Stop all services
```bash
docker compose down
```

### View logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f lpr-app

# Specific profile
docker compose --profile proxy logs -f
```

## Network Architecture

All services are connected to the `openlpr-network` bridge network:

- **Internal communication**: Services use DNS names (e.g., `http://lpr-app:8000`)
- **External access**: Via exposed ports or proxy routing
- **No proxy needed**: Services communicate with each other regardless of proxy profile

Example internal communication:
- Prometheus scrapes metrics from `http://lpr-app:8000/metrics`
- Blackbox exporter probes `http://lpr-app:8000/health`
- Canary tests `http://lpr-app:8000/api/v1/ocr/`
- Grafana connects to `http://prometheus:9090`

This internal communication works with or without the Traefik proxy enabled.