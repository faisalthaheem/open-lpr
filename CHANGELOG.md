# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- Support for additional GPU types (NVIDIA CUDA)
- Batch processing capabilities
- Real-time video stream processing
- Additional language support for license plates
- Performance optimizations
- Mobile application