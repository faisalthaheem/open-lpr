# Open LPR v1.1.0 Release Notes

We're excited to announce Open LPR v1.1.0! This is a significant feature release that brings monitoring infrastructure, improved Docker deployment, UI enhancements, and numerous bug fixes.

## 🆕 Major Features

### Two-Phase LPR Pipeline with Dynamic Detection Scaling
The license plate recognition pipeline now uses a two-phase approach:
- **Phase 1**: Detects license plate bounding boxes in the full image
- **Phase 2**: Runs OCR on cropped plate regions for higher accuracy
- Dynamic scaling adjusts detection parameters based on image characteristics

### Comprehensive Monitoring Stack
Full observability stack with custom Docker images:
- **Prometheus** with LPR app metrics dashboard
- **Grafana** with pre-built dashboards for both the LPR app and canary service
- **Blackbox Exporter** for HTTP endpoint probing
- **Canary Service** for automated health checks and endpoint verification
- Custom monitoring images with embedded configurations, published to GHCR

### Profile-Based Docker Compose
Complete Docker Compose refactor using the merge design pattern with profiles:
- **core**: Core infrastructure (Traefik, OpenLPR, Prometheus, Grafana, Blackbox, Canary)
- **cpu**: CPU-based LlamaCpp inference
- **amd-vulkan**: AMD Vulkan GPU inference
- **nvidia-cuda**: NVIDIA CUDA GPU inference (new!)
- **proxy**: Optional Traefik reverse proxy

Individual compose files (`docker-compose-llamacpp-cpu.yml`, `docker-compose-llamacpp-amd-vulcan.yml`) are now deprecated.

### NVIDIA CUDA GPU Support
Local LlamaCpp inference now supports NVIDIA GPUs with CUDA, in addition to the existing AMD Vulkan and CPU options.

### Dark Mode
Comprehensive dark mode support with:
- Automatic system theme detection
- Smooth light/dark mode switching
- Proper styling for all UI components including OCR results and data tables

## ✨ New Features

- **Dynamic font scaling** for OCR text visualization on bounding boxes
- **Favicon** for the LPR application
- **Star History chart** added to README
- **Coolify deployment support** with custom Docker images
- **Configurable Traefik router rules** via environment variables
- **Configurable service ports** to avoid deployment conflicts
- **CSRF trusted origins** configuration for cross-origin requests
- **Simplified mobile pagination** for better mobile experience
- **Liability disclaimer** in application header
- **Live demo link** in README pointing to https://rest-openlpr.computedsynergy.com/

## 🔧 Changed

- **Code architecture**: Split monolithic `views.py` into modular view components (`views/` subpackage with `web_views.py`, `api_views.py`, `file_views.py`)
- **Homepage**: Now shows 9 processed images with annotations
- **Image list page**: Shows annotated images with OCR text and plate count instead of just filenames
- **UI layout**: Condensed vertical space for better screen utilization
- **Upload size**: Maximum reduced from 10MB to 250KB for optimized processing
- **README**: Reorganized with collapsible sections and compact navigation
- **License**: Changed from MIT to Apache 2.0

## 🐛 Bug Fixes

### Infrastructure Fixes
- Fixed `django.logstatic` typo in docker-entrypoint.sh causing `chown` error on startup
- Fixed metrics directory permissions by adding `/app/metrics` to Dockerfile
- Fixed metrics state file (`metrics_state.json`) creation and permissions in entrypoint
- Fixed database file ownership to prevent readonly database errors in containers
- Fixed multi-platform Docker build issue
- Fixed Traefik Docker API compatibility issue

### Monitoring Fixes
- Fixed canary service HTTP 502 error and connectivity issues
- Fixed canary image cleanup functionality
- Fixed canary dashboard configuration and connectivity
- Fixed Prometheus and Blackbox Exporter duplicate binary names in CMD
- Fixed Grafana provisioning duplicate UID warnings
- Fixed metrics endpoint errors

### Application Fixes
- Fixed hardcoded API response data in LPR processing
- Fixed KeyError in `get_first_ocr_text()` method for mixed OCR data formats
- Fixed OCR results display in dark mode
- Fixed pagination URL encoding and error handling
- Fixed reverse pagination on image list page
- Fixed duplicate timestamps (removed redundant ones)
- Fixed display of correct max file size on upload page
- Eliminated duplicate Traefik configuration
- Fixed navigation links in README.md

## 📦 Dependency Updates

| Package | From | To |
|---------|------|----|
| Django | 4.2.7 | 4.2.30 |
| Pillow | 10.1.0 | 12.2.0 |
| Gunicorn | 21.2.0 | 22.0.0 |
| python-dotenv | — | 1.2.2 |

## 🐳 Docker Images

The v1.1.0 release includes updated Docker images:

- `ghcr.io/faisalthaheem/open-lpr:latest` — Latest stable version (now v1.1.0)
- `ghcr.io/faisalthaheem/open-lpr:v1.1.0` — Version 1.1.0
- `ghcr.io/faisalthaheem/open-lpr:v1.1` — Version 1.1.x series
- `ghcr.io/faisalthaheem/open-lpr:v1` — Version 1.x series (latest minor)

Images are available for both **linux/amd64** and **linux/arm64** architectures.

## ⚠️ Deprecated

- Individual Docker Compose files (`docker-compose-llamacpp-cpu.yml`, `docker-compose-llamacpp-amd-vulcan.yml`)
- Migrate to profile-based approach: `docker compose --profile core --profile <inference-profile> up -d`

## 📋 API Changes

No breaking changes to the API in this release. All existing endpoints remain compatible with v1.0.0.

## 🔄 Upgrade Instructions

### Docker Deployment (Profile-Based — Recommended)

```bash
# Pull the latest images
docker compose pull

# Restart with your preferred profile
docker compose --profile core --profile <cpu|nvidia-cuda|amd-vulkan> up -d
```

### From Deprecated Individual Compose Files

```bash
# Old (deprecated)
docker compose -f docker-compose-llamacpp-cpu.yml pull
docker compose -f docker-compose-llamacpp-cpu.yml up -d

# New (recommended)
docker compose --profile core --profile cpu pull
docker compose --profile core --profile cpu up -d
```

### Source Installation

```bash
git fetch origin
git checkout v1.1.0
pip install -r requirements.txt
python manage.py migrate
# Restart your application server
```

## 🛠️ Migration Notes

- No database migrations required for this release
- All configuration files remain compatible
- No breaking changes to existing functionality
- If using deprecated individual compose files, migrate to profile-based approach

## 🐛 Known Issues

- Large images (>250KB) are rejected at upload to ensure optimal performance
- Some very old OCR data formats may require manual migration

## 🔒 Security

- Django security patches included through version 4.2.30
- Pillow security patches included through version 12.2.0
- Non-root Docker user maintained
- Input validation and sanitization maintained
- CSRF protection with trusted origins support

## 🙏 Acknowledgments

Thank you to all users who reported issues, provided feedback, and contributed to this release! Special thanks to Dependabot for keeping dependencies up to date.

## 📄 License

This project is licensed under the Apache License 2.0 — see the [LICENSE](LICENSE) file for details.

---

**Thank you for using Open LPR!** 🎉

If you encounter any issues or have questions, please [file an issue](https://github.com/faisalthaheem/open-lpr/issues) on GitHub.