# Open LPR v1.1.0

## 🆕 Major Features

### Two-Phase LPR Pipeline with Dynamic Detection Scaling
Improved accuracy with a two-phase approach: Phase 1 detects plate bounding boxes, Phase 2 runs OCR on cropped regions. Dynamic scaling adjusts parameters based on image characteristics.

### Comprehensive Monitoring Stack
Full observability with custom Docker images:
- **Prometheus** + **Grafana** with pre-built dashboards
- **Blackbox Exporter** for HTTP probing
- **Canary Service** for automated health checks
- All monitoring images published to GHCR

### Profile-Based Docker Compose
Simplified deployment with merge design pattern profiles:
```bash
docker compose --profile core --profile <cpu|nvidia-cuda|amd-vulkan> up -d
```

### NVIDIA CUDA GPU Support
Local LlamaCpp inference now supports NVIDIA GPUs alongside existing AMD Vulkan and CPU options.

### Dark Mode
System-aware dark/light mode with automatic switching across all UI components.

## ✨ Also New
- Dynamic font scaling for OCR text visualization
- Favicon for the LPR application
- Coolify deployment support
- Configurable Traefik router rules and service ports
- CSRF trusted origins configuration
- Live demo at https://rest-openlpr.computedsynergy.com/

## 🔧 Changed
- Split monolithic `views.py` into modular view components
- Django 4.2.7 → 4.2.30, Pillow 10.1.0 → 12.2.0, Gunicorn 21.2.0 → 22.0.0
- Upload size optimized from 10MB to 250KB
- License changed to Apache 2.0

## 🐛 Bug Fixes
- Fixed `django.logstatic` typo in entrypoint causing startup error
- Fixed metrics directory and state file permissions in Docker
- Fixed canary service connectivity and image cleanup
- Fixed Prometheus/Grafana/Blackbox configuration issues
- Fixed database file ownership in containers
- Fixed hardcoded API response data in LPR processing
- Fixed OCR display in dark mode, pagination, timestamps, and more

## ⚠️ Deprecated
- Individual Docker Compose files — migrate to profile-based approach

## 📋 API Changes
No breaking changes. All v1.0.0 endpoints remain compatible.

## 🐳 Docker Images
- `ghcr.io/faisalthaheem/open-lpr:v1.1.0`
- `ghcr.io/faisalthaheem/open-lpr:v1.1`
- `ghcr.io/faisalthaheem/open-lpr:v1`
- `ghcr.io/faisalthaheem/open-lpr:latest`

Multi-arch: linux/amd64 + linux/arm64

**Full Release Notes**: See [RELEASE_NOTES_v1.1.0.md](docs/RELEASE_NOTES_v1.1.0.md) and [CHANGELOG.md](CHANGELOG.md)