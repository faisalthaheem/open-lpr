# Docker Compose Profiles for OpenLPR

This document describes the refactored Docker Compose setup using the merge design pattern with profiles.

## Profiles

### Core Profile (`core`)
Contains the core infrastructure services:
- **traefik**: Reverse proxy with dashboard (http://traefik.localhost)
- **lpr-app**: Main Django application (http://lpr.localhost)
- **prometheus**: Monitoring system (http://prometheus.localhost)
- **grafana**: Visualization dashboard (http://grafana.localhost)

### Inference Profiles
Choose one based on your hardware:

#### CPU Profile (`cpu`)
- **llamacpp-cpu**: CPU-based inference server

#### AMD Vulkan Profile (`amd-vulkan`)
- **llamacpp-amd-vulkan**: AMD GPU inference with Vulkan support

#### NVIDIA CUDA Profile (`nvidia-cuda`)
- **llamacpp-nvidia-cuda**: NVIDIA GPU inference with CUDA support

## Usage Examples

### Start with Core Infrastructure + CPU Inference
```bash
docker-compose --profile core --profile cpu up -d
```

### Start with Core Infrastructure + NVIDIA Inference
```bash
docker-compose --profile core --profile nvidia-cuda up -d
```

### Start with Core Infrastructure + AMD Vulkan Inference
```bash
docker-compose --profile core --profile amd-vulkan up -d
```

### Start Only Core Services
```bash
docker-compose --profile core up -d
```

### Stop All Services
```bash
docker-compose down
```

## Environment Configuration

Copy the example environment file:
```bash
cp .env.llamacpp.example .env.llamacpp
```

Edit `.env.llamacpp` with your specific configuration:
- HuggingFace token for model downloads
- Django settings (SECRET_KEY, DEBUG, etc.)
- Grafana credentials
- Model configuration

## Access Points

After starting the services:

- **OpenLPR Application**: http://lpr.localhost
- **Traefik Dashboard**: http://traefik.localhost
- **Prometheus**: http://prometheus.localhost
- **Grafana**: http://grafana.localhost (admin/admin by default)

## Service Dependencies

- `lpr-app` depends on a healthy inference service (when inference profiles are active)
- All services share the `openlpr-network` for communication
- Volumes are shared for data persistence

## Monitoring

The setup includes comprehensive monitoring:
- **Prometheus** collects metrics from all services
- **Grafana** provides visualization dashboards
- **Traefik** provides request metrics and routing

## Hardware Requirements

### CPU Profile
- Any modern CPU with sufficient RAM
- Recommended: 8GB+ RAM for model loading

### AMD Vulkan Profile
- AMD GPU with Vulkan support
- Proper GPU drivers installed
- Access to `/dev/dri` and `/dev/kfd` devices

### NVIDIA CUDA Profile
- NVIDIA GPU with CUDA support
- NVIDIA Container Toolkit installed
- Proper GPU drivers

## Development vs Production

### Development
- Uses localhost domains
- Debug mode enabled
- Basic authentication only

### Production (TODO)
- Configure proper domains
- Set up SSL certificates
- Secure authentication
- Resource limits
- Backup strategies

## Troubleshooting

### Common Issues

1. **Port Conflicts**: Ensure ports 80, 8080, 3000, 9090, 8000, 8001 are available
2. **GPU Access**: Verify GPU drivers and container runtime for GPU profiles
3. **Permission Issues**: Check Docker socket access for Traefik
4. **Model Downloads**: Verify HuggingFace token and network access

### Health Checks

All services include health checks. Monitor with:
```bash
docker-compose ps
docker-compose logs [service-name]
```

## Migration from Old Setup

The old separate compose files are deprecated. To migrate:
1. Backup existing data in `container-data` and `container-media`
2. Update environment file format
3. Use new profile commands to start services
4. Verify all functionality works as expected

## Customization

### Adding New Services
Add services to `docker-compose.yml` with appropriate profiles and labels.

### Modifying Routes
Update `traefik/dynamic/config.yml` for custom routing rules.

### Monitoring Configuration
Modify `prometheus/prometheus.yml` and Grafana provisioning files for custom metrics.
