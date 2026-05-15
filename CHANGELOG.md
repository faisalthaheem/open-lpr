# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-05-15

### Added
- Two-phase LPR pipeline with dynamic detection scaling for improved accuracy
- Comprehensive canary monitoring system with automated health checks
- Profile-based Docker Compose with merge design pattern (replaces individual compose files)
- Custom monitoring Docker images (Prometheus, Grafana, Blackbox Exporter) with embedded configs
- GitHub Actions workflow for building and publishing monitoring images
- NVIDIA CUDA GPU support for local LlamaCpp inference
- AMD Vulkan GPU support for local LlamaCpp inference
- Dark mode support with system theme detection and automatic switching
- Dynamic font scaling for OCR text visualization
- Favicon for the LPR application
- Star History chart in README
- Coolify deployment support with custom Docker images
- Configurable Traefik router rules via environment variables
- Configurable service ports to avoid conflicts
- CSRF trusted origins configuration for cross-origin requests
- Prometheus monitoring with LPR app dashboard
- Grafana dashboards for both LPR app and canary service
- Blackbox exporter for HTTP probing
- Simplified mobile pagination
- Liability disclaimer in application header
- Live demo link in README

### Changed
- Split monolithic `views.py` into modular view components (`views/` subpackage)
- Django upgraded from 4.2.7 to 4.2.30
- Pillow upgraded from 10.1.0 to 12.2.0
- Gunicorn upgraded from 21.2.0 to 22.0.0
- python-dotenv upgraded to 1.2.2
- License changed to Apache 2.0
- Maximum image upload size reduced from 10MB to 250KB for optimized processing
- Homepage updated to show 9 processed images with annotations
- UI condensed for better screen utilization
- Image list page now shows annotated images with OCR text and plate count
- README reorganized with collapsible sections and compact navigation

### Fixed
- Fixed `django.logstatic` typo in docker-entrypoint.sh causing chown error on startup
- Fixed metrics directory permissions by adding `/app/metrics` to Dockerfile
- Fixed metrics state file (`metrics_state.json`) creation and permissions in entrypoint
- Fixed canary service HTTP 502 error and connectivity issues
- Fixed canary image cleanup functionality
- Fixed canary dashboard configuration and connectivity
- Fixed Prometheus and Blackbox Exporter duplicate binary names in CMD
- Fixed Grafana provisioning duplicate UID warnings
- Fixed metrics endpoint errors
- Fixed multi-platform Docker build issue
- Fixed Traefik Docker API compatibility issue
- Fixed database file ownership to prevent readonly database errors
- Fixed hardcoded API response data in LPR processing
- Fixed KeyError in `get_first_ocr_text()` method
- Fixed OCR results display in dark mode
- Fixed pagination URL encoding and error handling
- Fixed reverse pagination on image list page
- Fixed duplicate timestamps (removed redundant ones)
- Fixed display of correct max file size on upload page
- Eliminated duplicate Traefik configuration
- Fixed navigation links in README.md

### Deprecated
- Individual Docker Compose files (`docker-compose-llamacpp-cpu.yml`, `docker-compose-llamacpp-amd-vulcan.yml`)
- Use profile-based approach with main `docker-compose.yml` instead

### Security
- Django security patches included in upgrade to 4.2.30
- Pillow security patches included in upgrade to 12.2.0
- Non-root Docker user maintained
- Input validation and sanitization maintained
- CSRF protection with trusted origins support

## [1.0.0] - 2025-11-23

### Added
- Initial release of Open LPR - License Plate Recognition System
- Django-based web application with license plate recognition capabilities
- RESTful API with comprehensive endpoints for image processing
- User-friendly web interface with drag-and-drop upload functionality
- Image processing pipeline with bounding box visualization
- Search and filter functionality for processed images
- Responsive design that works across all devices
- Docker deployment support with optimized multi-stage Dockerfile
- Automated CI/CD pipeline with GitHub Actions
- Multi-architecture support (linux/amd64, linux/arm64)
- Automatic publishing to GitHub Container Registry
- Software Bill of Materials (SBOM) generation for security scanning
- Local inference support with LlamaCpp server
- CPU and GPU deployment options for LlamaCpp
- Comprehensive documentation for local deployment
- Environment configuration templates
- Model download automation
- Visual showcase with screenshots in documentation
- API documentation with detailed endpoint descriptions
- Docker deployment guide with multiple deployment options
- LlamaCpp and ROCm resources collection
- Troubleshooting guides and best practices

### Features
- AI-powered detection using qwen3-vl-4b-instruct vision-language model
- Advanced OCR integration with confidence scores
- Bounding box visualization for detected plates and OCR text
- Permanent storage of uploaded and processed images
- Side-by-side comparison of original and processed images
- Health check endpoint for monitoring
- Download functionality for original and processed images
- Processing status tracking with AJAX endpoints
- Comprehensive error handling and logging
- Security best practices including non-root Docker user
- Environment-based configuration management
- Input validation and sanitization

### Documentation
- Comprehensive README with visual showcase
- Detailed API documentation
- Docker deployment guide
- LlamaCpp deployment guide
- LlamaCpp and ROCm resources collection
- Contributing guidelines
- Code style guidelines

### Technical Details
- Django 4.x web framework
- Bootstrap 5 for responsive UI
- Gunicorn WSGI server for production
- SQLite database with migration support
- Docker containerization with multi-stage builds
- GitHub Actions for CI/CD
- Semantic versioning with automated tagging
- SBOM generation for security scanning

### Security
- Non-root Docker user for security
- Environment-based configuration
- Secure file upload handling
- Input validation and sanitization
- CSRF protection
- Security headers configuration

### Performance
- Optimized Docker image for production use
- Gunicorn WSGI server with 3 workers
- Efficient image processing pipeline
- Configurable batch processing
- Multi-architecture Docker images

### Developer Experience
- Well-structured codebase following Django best practices
- Comprehensive documentation
- Environment configuration templates
- Management commands for project setup
- Clear code organization with separation of concerns

### Deployment
- Standard Docker deployment with cloud-based AI services
- LlamaCpp CPU deployment for local inference
- LlamaCpp GPU deployment with AMD Vulkan support
- Environment configuration templates
- Automated model download
- Health checks and monitoring

### API Endpoints
- Web endpoints for user interface
- REST API endpoints for programmatic access
- Health check endpoint
- File upload and processing endpoints
- Image download endpoints
- Search and filtering endpoints

### Known Limitations
- Large images (>10MB) may require increased memory allocation
- GPU acceleration is currently limited to AMD GPUs with Vulkan support
- Concurrent processing is limited by Django's development server (use Gunicorn in production)

### Dependencies
- Django 4.x
- Bootstrap 5
- Gunicorn
- Docker
- LlamaCpp (for local inference)
- Qwen3-VL model

### License
- MIT License

---

## [Unreleased]

### Planned
- Batch processing capabilities
- Real-time video stream processing
- Additional language support for license plates
- Performance optimizations
- Mobile application